"""
LINE Bot with Google Imagen 3 Integration
Generates AI images based on user text messages using Google's latest Imagen 3 model.
"""

import os
import io
import logging
import threading
from collections import deque
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

# Load environment variables and strip whitespace
load_dotenv()

def get_env_stripped(key, default=None):
    val = os.getenv(key, default)
    return val.strip() if val else val

# Configure logging with buffer for remote debugging
log_buffer = deque(maxlen=100)

class BufferHandler(logging.Handler):
    def emit(self, record):
        log_buffer.append(self.format(record))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

buffer_handler = BufferHandler()
buffer_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(buffer_handler)
logging.getLogger('linebot').addHandler(buffer_handler) # Also capture line-bot logs

# Initialize Flask app
app = Flask(__name__)

# LINE Bot configuration
line_access_token = get_env_stripped('LINE_CHANNEL_ACCESS_TOKEN')
line_channel_secret = get_env_stripped('LINE_CHANNEL_SECRET')

line_configuration = Configuration(access_token=line_access_token)
handler = WebhookHandler(line_channel_secret)

# Google AI configuration
google_api_key = get_env_stripped('GOOGLE_API_KEY')
genai_client = genai.Client(api_key=google_api_key)

# Cloudinary configuration
cloudinary_url = get_env_stripped('CLOUDINARY_URL')
if cloudinary_url:
    cloudinary.config(cloudinary_url=cloudinary_url)
else:
    logger.warning("CLOUDINARY_URL is missing!")


@app.route("/", methods=['GET'])
def health_check():
    """Health check endpoint"""
    logger.info("--- HEALTH CHECK PINGED ---")
    return "LINE Bot is running! 🤖✨", 200


@app.route("/debug", methods=['GET'])
def debug_status():
    """Diagnostic endpoint to check if environment variables are set"""
    keys_to_check = [
        'LINE_CHANNEL_ACCESS_TOKEN', 
        'LINE_CHANNEL_SECRET', 
        'GOOGLE_API_KEY', 
        'CLOUDINARY_URL'
    ]
    status = {}
    for key in keys_to_check:
        val = os.getenv(key)
        if val:
            status[key] = f"SET (Len: {len(val)})"
        else:
            status[key] = "MISSING"
    
    status['log_count'] = len(log_buffer)
    status['server_time'] = os.popen('date').read().strip()
    return status, 200


@app.route("/logs", methods=['GET'])
def view_logs():
    """Endpoint to view the last 100 log lines as JSON"""
    return {"logs": list(log_buffer)}, 200


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
        logger.info("Signature verification and handling body...")
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("INVALID SIGNATURE. Check your LINE_CHANNEL_SECRET.")
        abort(400)
    except Exception as e:
        logger.error(f"UNEXPECTED ERROR in callback: {str(e)}", exc_info=True)
        return 'Internal Server Error', 500

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    """Handle incoming text messages and generate images"""
    user_message = event.message.text
    user_id = event.source.user_id
    reply_token = event.reply_token
    
    print(f"DEBUG: MATCHED TextMessage: {user_message}")
    logger.info(f"MATCHED: TextMessageEvent from {user_id}: {user_message}")
    
    # Send immediate response to acknowledge receipt
    with ApiClient(line_configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        try:
            print(f"DEBUG: Replying to token {reply_token}...")
            # Reply with acknowledgment
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="🎨 画像を生成中です... しばらくお待ちください")]
                )
            )
            print("DEBUG: Reply sent.")
            
            # Synchronous for debugging
            generate_and_send_image(user_id, user_message)
            
        except Exception as e:
            print(f"DEBUG ERROR in handler: {str(e)}")
            logger.error(f"CRITICAL in handle_text_message: {str(e)}", exc_info=True)
            try:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[TextMessage(text=f"❌ システムエラーが発生しました:\n{str(e)}")]
                    )
                )
            except Exception as reply_err:
                logger.error(f"Double crash: {str(reply_err)}")


@handler.default()
def default_handler(event):
    """Diagnostic handler for all other events"""
    logger.info(f"RECEIVED OTHER EVENT: {type(event).__name__}")
    logger.info(f"Event details: {event}")


def generate_and_send_image(user_id: str, prompt: str):
    """Generate image using Google Imagen 3 and send to user"""
    try:
        logger.info(f"Generating image with prompt: {prompt}")
        
        # Generate image using Imagen 4
        # Requires billing to be enabled in Google Cloud Project
        response = genai_client.models.generate_images(
            model='imagen-4.0-generate-001',
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
        logger.info("Uploading image to Cloudinary...")
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
