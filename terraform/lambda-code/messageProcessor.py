import json
import boto3
import os
import requests
from datetime import datetime
import re

AWS_REGION = "us-east-1"

# AWS Clients
comprehend = boto3.client("comprehend", region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)

flagged_table = dynamodb.Table("FlaggedMessages")
user_table = dynamodb.Table("UserFlagCounts")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

FLAG_THRESHOLD = 3  # Warning after 3 flags

# -------- Escape Markdown --------
def escape_markdown(text):
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

# -------- Sentiment Analysis --------
def analyze_sentiment(text):
    try:
        response = comprehend.detect_sentiment(Text=text, LanguageCode="en")
        sentiment = response["Sentiment"]
        print(f"✅ Sentiment: {sentiment}")
        return sentiment
    except Exception as e:
        print("❌ Comprehend error:", str(e))
        return "UNKNOWN"

# -------- Store Message in DynamoDB --------
def store_in_dynamodb(message_id, chat_id, text, sentiment, username, group_name):
    item = {
        "MessageID": str(message_id),
        "UserID": str(chat_id),
        "Username": username or "Unknown",
        "GroupName": group_name or "Private Chat",
        "MessageText": text,
        "Sentiment": sentiment,
        "Timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
    }

    print("📝 Writing to FlaggedMessages:", item)
    try:
        flagged_table.put_item(Item=item)
        print("✅ Stored in FlaggedMessages table")
    except Exception as e:
        print("❌ Error storing in FlaggedMessages:", str(e))

# -------- Update or Create User Flag Count with Context --------
def increment_flag_count(user_id, username, group_name, chat_type):
    try:
        # Convert user_id to a string (if not already)
        user_id_str = str(user_id)
        # Use a default value for group_name if not provided
        group_name_val = group_name or "Private Chat"
        
        # Define the key using both UserID (partition key) and GroupName (sort key)
        key = {"UserID": user_id_str, "GroupName": group_name_val}
        
        # Retrieve the item with this composite key
        response = user_table.get_item(Key=key)
        
        if "Item" in response:
            # If the item exists, update the flag count and other attributes
            update_response = user_table.update_item(
                Key=key,
                UpdateExpression="SET Username = :uname, ChatType = :ctype ADD FlagCount :inc",
                ExpressionAttributeValues={
                    ":inc": 1,
                    ":uname": username,
                    ":ctype": chat_type
                },
                ReturnValues="UPDATED_NEW"
            )
            updated_count = update_response["Attributes"]["FlagCount"]
            print(f"✅ FlagCount updated for UserID: {user_id_str} in Group: {group_name_val} → New Count: {updated_count}")
            return updated_count
        else:
            # If the record doesn't exist, create a new one with an initial flag count of 1
            new_item = {
                "UserID": user_id_str,
                "GroupName": group_name_val,
                "Username": username,
                "ChatType": chat_type,
                "FlagCount": 1
            }
            user_table.put_item(Item=new_item)
            print(f"🆕 Created new user entry for UserID: {user_id_str} in Group: {group_name_val}")
            return 1
    except Exception as e:
        print(f"❌ Failed to update/create flag count for UserID: {user_id} in Group: {group_name} → {e}")
        return 0

# -------- Send Telegram Message --------
def send_telegram_message(chat_id, text):
    try:
        payload = {"chat_id": chat_id, "text": text}
        response = requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload)
        print("✅ Telegram message sent:", response.json())
    except Exception as e:
        print("❌ Telegram sendMessage failed:", str(e))

# -------- Send Admin Panel --------
def send_admin_panel(chat_id):
    keyboard = {
        "inline_keyboard": [[
            {"text": "View Flagged Messages", "callback_data": "view_flagged"}
        ]]
    }
    payload = {
        "chat_id": chat_id,
        "text": "🛠 Admin Panel:\nChoose an action:",
        "reply_markup": keyboard  # Pass as raw dict
    }
    try:
        response = requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload)
        print("✅ Admin panel sent:", response.json())
    except Exception as e:
        print("❌ Failed to send admin panel:", str(e))

# -------- View Summary Callback --------
def handle_summary_request(chat_id, chat_type):
    try:
        is_private = chat_type == "private"

        flagged_items = flagged_table.scan().get("Items", [])
        user_count_items = user_table.scan().get("Items", [])

        # Filter based on chat type
        relevant_flagged = []
        relevant_user_ids = set()

        for item in flagged_items:
            if is_private and item.get("GroupName") == "Private Chat" and item.get("UserID") == str(chat_id):
                relevant_flagged.append(item)
                relevant_user_ids.add(item["UserID"])
            elif not is_private and item.get("UserID") == str(chat_id):
                relevant_flagged.append(item)
                relevant_user_ids.add(item["UserID"])

        flagged_summary = {}
        for item in relevant_flagged:
            user = item.get("Username", "Unknown")
            group = item.get("GroupName", "Private Chat")
            label = "Group" if group != "Private Chat" else "Private"
            key = f"{user} ({label})"
            flagged_summary[key] = flagged_summary.get(key, 0) + 1

        message = "📊 *Flagged Message Summary:*\n"
        if not flagged_summary:
            message += "\n📭 No flagged messages found."
        else:
            for user_key, count in flagged_summary.items():
                message += f"\n👤 {user_key}: {count} flagged message(s)"

        # Filter flag count users (if needed for additional processing)
        filtered_user_counts = [
            user for user in user_count_items if user["UserID"] in relevant_user_ids
        ]

        message = escape_markdown(message)

        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "MarkdownV2"
        }

        print("📤 Sending to Telegram → payload:")
        print(json.dumps(payload, indent=2))

        response = requests.post(f"{TELEGRAM_API_URL}/sendMessage", json=payload)
        print("📬 Telegram response:", response.status_code, response.text)

    except Exception as e:
        print("❌ Failed to send summary:", str(e))

# -------- Main Lambda Handler --------
def lambda_handler(event, context):
    print("📦 Lambda Triggered Event:")
    print(json.dumps(event, indent=2))

    if event.get("httpMethod") == "GET":
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "GET not implemented"})
        }

    body = json.loads(event.get("body", "{}"))

    # Handle Callback Query
    if "callback_query" in body:
        callback = body["callback_query"]
        chat_id = callback["message"]["chat"]["id"]
        chat_type = callback["message"]["chat"]["type"]
        callback_id = callback["id"]
        data = callback.get("data")

        print(f"✅ Callback received → data: {data} | chat_id: {chat_id} | type: {chat_type}")
        requests.post(f"{TELEGRAM_API_URL}/answerCallbackQuery", json={"callback_query_id": callback_id})

        if data == "view_flagged":
            handle_summary_request(chat_id, chat_type)

        return {"statusCode": 200}

    # Handle Text Message
    message = body.get("message")
    if not message:
        print("❌ No message in event body.")
        return {"statusCode": 200}

    chat_id = message["chat"]["id"]
    chat_type = message["chat"]["type"]
    message_id = message.get("message_id")
    text = message.get("text", "")
    username = message.get("from", {}).get("username", "Unknown")
    group_name = message.get("chat", {}).get("title", "Private Chat")

    # Handle the /review command (supports variations like "/review@YourBotName")
    if text.strip().lower().startswith("/review"):
        send_admin_panel(chat_id)
        return {"statusCode": 200}

    print("\n📥 New Message:")
    print(f"👤 @{username} | 🆔 {chat_id} | Type: {chat_type}")
    print(f"👥 Group: {group_name}")
    print(f"💬 Message: {text}")

    sentiment = analyze_sentiment(text)
    print(f"🧠 Sentiment → {sentiment}")

    # Process flagged messages
    if sentiment in ["NEGATIVE", "MIXED"]:
        store_in_dynamodb(message_id, chat_id, text, sentiment, username, group_name)
        flag_count = increment_flag_count(chat_id, username, group_name, chat_type)
        
        # Use a fallback display name if username is "Unknown"
        display_name = username if username != "Unknown" else "User"
        
        # Send a warning once the flag count reaches the threshold
        if flag_count >= FLAG_THRESHOLD:
            warning = f"⚠️ Warning, @{display_name}! Your message has been flagged for this chat. Please follow the rules."
            send_telegram_message(chat_id, warning)

    return {"statusCode": 200}
