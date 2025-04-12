# 🛡️ ToxiTrack – Serverless Telegram Moderator

ToxiTrack is a fully serverless Telegram moderation bot using AWS Lambda, Amazon Comprehend, DynamoDB, and SNS to detect toxic messages and alert admins.

## 📦 Project Structure

- Terraform-based deployment of AWS resources
- Python-based Lambda for Telegram message handling
- Amazon Comprehend for sentiment detection
- Telegram Bot API for user interaction

## 🚀 Deployment with Terraform

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/toxiTrack-telegram-moderator.git
cd toxiTrack-telegram-moderator/terraform
```

### 2. Prepare Lambda Code

Ensure your zipped Lambda is placed at `terraform/lambda/messageProcessor.zip`

```bash
cd ../lambda-code
zip ../terraform/lambda/messageProcessor.zip messageProcessor.py
```

### 3. Deploy Infrastructure

```bash
terraform init
terraform apply -var="telegram_bot_token=YOUR_BOT_TOKEN"
```

---

## 🤖 How to Create a Telegram Bot Token

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Start a chat and type `/newbot`
3. Follow the prompts to name your bot and get the token
4. Copy the token and use it in the Terraform command above

---

## 🧠 AWS Services Used

- **Lambda** – Executes message processing logic
- **DynamoDB** – Stores flagged messages and user history
- **Amazon Comprehend** – Detects message sentiment
- **SNS** – Sends alert notifications
- **IAM** – Role-based permissions for Lambda

---

## 📸 Screenshots

> ![Architecture Diagram](./assets/architecture.png)
![Group Chat](./assets/group-demo.png)
![Private Chat](./assets/private-demo.png)


---