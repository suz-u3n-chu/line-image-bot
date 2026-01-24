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
            if "api_key" in val or "your_" in val:
                 status[key] = f"WARNING: Likely Placeholder (Len: {len(val)})"
            else:
                 status[key] = f"SET (Len: {len(val)})"
        else:
            status[key] = "MISSING"
    
    status['log_count'] = len(log_buffer)
    status['server_time'] = os.popen('date').read().strip()
    
    # Check Cloudinary configuration detail
    if cloudinary_url:
        try:
            # Simple parsing of cloudinary://key:secret@cloudname
            parts = cloudinary_url.split('@')
            if len(parts) > 1:
                status['cloudinary_cloud_name'] = parts[1]
            else:
                status['cloudinary_cloud_name'] = "INVALID_FORMAT (MISSING_@)"
        except Exception:
            status['cloudinary_cloud_name'] = "PARSE_ERROR"
            
    return status, 200


@app.route("/logs", methods=['GET'])
def view_logs():
    """Endpoint to view the last 100 log lines as JSON"""
    return {"logs": list(log_buffer)}, 200


@app.route("/callback", methods=['POST'])
def callback():
    """LINE webhook callback endpoint"""
    print(">>> CALLBACK RECEIVED <<<")
    # Get X-Line-Signature header value
    signature = request.headers.get('X-Line-Signature')
    if not signature:
        print("ERROR: No signature header")
        abort(400)

    # Get request body as text
    body = request.get_data(as_text=True)
    print(f"DEBUG: Body length: {len(body)}")
    logger.info(f"Request body: {body}")

    # Handle webhook body
    try:
        print("DEBUG: Verifying signature...")
        handler.handle(body, signature)
        print("DEBUG: Handler finished successfully")
    except InvalidSignatureError:
        print("ERROR: Invalid signature")
        logger.error("INVALID SIGNATURE. Check your LINE_CHANNEL_SECRET.")
        abort(400)
    except Exception as e:
        print(f"ERROR: Unexpected error in callback: {str(e)}")
        logger.error(f"UNEXPECTED ERROR in callback: {str(e)}", exc_info=True)
        return 'Internal Server Error', 500

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    """Handle incoming text messages and generate images"""
    print(">>> HANDLER: handle_text_message triggered <<<")
    user_message = event.message.text
    user_id = event.source.user_id
    reply_token = event.reply_token
    
    print(f"DEBUG: Message content: '{user_message}' from {user_id}")
    logger.info(f"MATCHED: TextMessageEvent from {user_id}: {user_message}")
    
    # Send immediate response to acknowledge receipt
    with ApiClient(line_configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        try:
            print("DEBUG: Reply sent. Starting background thread...")
            
            # Use background thread again to prevent LINE timeouts
            thread = threading.Thread(target=generate_and_send_image, args=(user_id, user_message))
            thread.start()
            
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
    """Generate image using Google AI and send to user"""
    try:
        print(f"DEBUG: Generating image for prompt: '{prompt}'")
        
        # Step 1: AI Image Generation
        try:
            response = genai_client.models.generate_images(
                model='imagen-4.0-generate-001',
                prompt=prompt,
                config=types.GenerateImagesConfig(number_of_images=1)
            )
            if not response.generated_images:
                raise ValueError("Google AI returned no images")
            image_bytes = response.generated_images[0].image.image_bytes
            print("DEBUG: AI generation SUCCESS")
        except Exception as gen_err:
            print(f"DEBUG: AI Generation FAILED: {str(gen_err)}")
            raise Exception(f"Google AI画像生成エラー: {str(gen_err)}")
        
        # Step 2: Cloudinary Upload
        try:
            print("DEBUG: Uploading to Cloudinary...")
            upload_result = cloudinary.uploader.upload(
                io.BytesIO(image_bytes),
                folder="line-bot-images",
                resource_type="image"
            )
            image_url = upload_result.get('secure_url')
            if not image_url:
                raise ValueError("Cloudinary returned no URL")
            print(f"DEBUG: Upload SUCCESS: {image_url}")
        except Exception as up_err:
            print(f"DEBUG: Cloudinary Upload FAILED: {str(up_err)}")
            # Specifically check for the common placeholder error
            detailed_err = str(up_err)
            if "api_key" in detailed_err.lower():
                detailed_err += " (CloudinaryのURL設定が初期値のままの可能性があります)"
            raise Exception(f"Cloudinaryアップロードエラー: {detailed_err}")
        
        # Step 3: LINE Push Message
        try:
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
            print("DEBUG: LINE Push SUCCESS")
        except Exception as line_err:
            print(f"DEBUG: LINE Push FAILED: {str(line_err)}")
            raise Exception(f"LINE送信エラー: {str(line_err)}")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Worker Error: {error_msg}")
        
        # Send FINAL error message to user via Push API
        try:
            with ApiClient(line_configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[TextMessage(text=f"❌ 処理中にエラーが発生しました:\n{error_msg}")]
                    )
                )
        except Exception as final_err:
            logger.error(f"Could not even send final error: {str(final_err)}")


if __name__ == "__main__":
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
