"""
LINE Bot with Google Imagen 3 Integration
Generates AI images based on user text messages using Google's latest Imagen 3 model.
"""

import os
import io
import logging
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
    ImageMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from google import genai
from google.genai import types
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# LINE Bot configuration
line_configuration = Configuration(access_token=os.getenv('LINE_CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.getenv('LINE_CHANNEL_SECRET'))

# Google AI configuration
genai_client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

# Cloudinary configuration
cloudinary.config(cloudinary_url=os.getenv('CLOUDINARY_URL'))


@app.route("/", methods=['GET'])
def health_check():
    """Health check endpoint"""
    return "LINE Bot is running! 🤖✨", 200


@app.route("/callback", methods=['POST'])
def callback():
    """LINE webhook callback endpoint"""
    # Get X-Line-Signature header value
    signature = request.headers.get('X-Line-Signature')
    if not signature:
        abort(400)

    # Get request body as text
    body = request.get_data(as_text=True)
    logger.info(f"Request body: {body}")

    # Handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature. Check your channel secret.")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    """Handle incoming text messages and generate images"""
    user_message = event.message.text
    user_id = event.source.user_id
    
    logger.info(f"Received message from {user_id}: {user_message}")
    
    # Send immediate response to acknowledge receipt
    with ApiClient(line_configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        try:
            # Reply with acknowledgment
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="🎨 画像を生成中です... しばらくお待ちください")]
                )
            )
            
            # Generate image asynchronously
            generate_and_send_image(user_id, user_message)
            
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=f"❌ エラーが発生しました: {str(e)}")]
                )
            )


def generate_and_send_image(user_id: str, prompt: str):
    """Generate image using Google Imagen 3 and send to user"""
    try:
        logger.info(f"Generating image with prompt: {prompt}")
        
        # Generate image using Imagen 3
        # Updated to use newer model version to avoid 404
        response = genai_client.models.generate_images(
            model='imagen-3.0-generate-002',
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                # Optional: Configure additional parameters
                # aspect_ratio='1:1',  # Options: '1:1', '3:4', '4:3', '9:16', '16:9'
                # safety_filter_level='block_some',  # Options: 'block_some', 'block_few', 'block_fewest'
            )
        )
        
        # Get the generated image
        if not response.generated_images:
            raise ValueError("No image was generated")
        
        generated_image = response.generated_images[0]
        image_bytes = generated_image.image.image_bytes
        
        logger.info("Image generated successfully")
        
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            io.BytesIO(image_bytes),
            folder="line-bot-images",
            resource_type="image"
        )
        
        image_url = upload_result.get('secure_url')
        logger.info(f"Image uploaded to Cloudinary: {image_url}")
        
        # Send image to user via Push API
        with ApiClient(line_configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[
                        TextMessage(text=f"✨ 画像が生成されました！\n\nプロンプト: {prompt}"),
                        ImageMessage(
                            original_content_url=image_url,
                            preview_image_url=image_url
                        )
                    ]
                )
            )
        
        logger.info(f"Image sent to user {user_id}")
        
    except Exception as e:
        logger.error(f"Error generating image: {str(e)}")
        
        # Send error message to user
        try:
            with ApiClient(line_configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[TextMessage(text=f"❌ 画像生成中にエラーが発生しました:\n{str(e)}")]
                    )
                )
        except Exception as push_error:
            logger.error(f"Error sending error message: {str(push_error)}")


if __name__ == "__main__":
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
