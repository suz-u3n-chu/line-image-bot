"""
LINE Bot with Google Imagen 3 Integration
Generates AI images based on user text messages using Google's latest Imagen 3 model.
"""

import os
import io
import logging
import threading
from collections import deque
from datetime import datetime, timedelta
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    PushMessageRequest,
    TextMessage,
    ImageMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent
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

# User image context storage (in-memory)
# Structure: {user_id: {"image_bytes": bytes, "timestamp": datetime}}
user_image_context = {}


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
    
    # Explicitly check the environment for the cloud name part
    c_url = os.getenv('CLOUDINARY_URL')
    if c_url:
        try:
            # Simple parsing of cloudinary://key:secret@cloudname
            if '@' in c_url:
                status['cloudinary_cloud_name_detected'] = c_url.split('@')[-1]
            else:
                status['cloudinary_cloud_name_detected'] = "MISSING_@_IN_URL"
        except Exception as e:
            status['cloudinary_cloud_name_detected'] = f"ERROR: {str(e)}"
            
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
            print(f"DEBUG: Sending immediate reply to token {reply_token}...")
            # Reply with acknowledgment
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="🎨 画像を生成中です... しばらくお待ちください")]
                )
            )
            print("DEBUG: Reply sent. Starting background thread...")
            
            # Check if user has a reference image stored
            cleanup_old_contexts()  # Clean up expired contexts
            
            if user_id in user_image_context:
                # Use reference image + prompt mode
                print(f"DEBUG: Found reference image for user {user_id}, using image-to-image mode")
                reference_bytes = user_image_context[user_id]["image_bytes"]
                thread = threading.Thread(
                    target=generate_image_with_reference, 
                    args=(user_id, user_message, reference_bytes)
                )
            else:
                # Use text-only mode
                print(f"DEBUG: No reference image for user {user_id}, using text-only mode")
                thread = threading.Thread(
                    target=generate_and_send_image, 
                    args=(user_id, user_message)
                )
            
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


def cleanup_old_contexts():
    """Remove image contexts older than 10 minutes"""
    current_time = datetime.now()
    expired_users = []
    
    for user_id, context in user_image_context.items():
        if current_time - context["timestamp"] > timedelta(minutes=10):
            expired_users.append(user_id)
    
    for user_id in expired_users:
        del user_image_context[user_id]
        logger.info(f"Cleaned up expired context for user {user_id}")


@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    """Handle incoming image messages and store them for later use"""
    print(">>> HANDLER: handle_image_message triggered <<<")
    user_id = event.source.user_id
    reply_token = event.reply_token
    message_id = event.message.id
    
    print(f"DEBUG: Image received from {user_id}, message_id: {message_id}")
    
    with ApiClient(line_configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        
        try:
            # Download image from LINE using MessagingApiBlob
            print(f"DEBUG: Downloading image {message_id}...")
            blob_api = MessagingApiBlob(api_client)
            image_content = blob_api.get_message_content(message_id)
            
            # Read image bytes
            image_bytes = image_content
            print(f"DEBUG: Image downloaded, size: {len(image_bytes)} bytes")
            
            # Store in context with timestamp
            cleanup_old_contexts()  # Clean up old contexts first
            user_image_context[user_id] = {
                "image_bytes": image_bytes,
                "timestamp": datetime.now()
            }
            
            # Send confirmation
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="📸 画像を受け取りました！\n次にプロンプトを送ってください。\n\n例：「この建物を夜景にして」「同じ構図で春の風景に」")]
                )
            )
            print(f"DEBUG: Image stored for user {user_id}")
            
        except Exception as e:
            print(f"DEBUG ERROR in image handler: {str(e)}")
            logger.error(f"Error handling image: {str(e)}", exc_info=True)
            try:
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[TextMessage(text=f"❌ 画像の処理中にエラーが発生しました:\n{str(e)}")]
                    )
                )
            except Exception as reply_err:
                logger.error(f"Failed to send error reply: {str(reply_err)}")


@handler.default()
def default_handler(event):
    """Diagnostic handler for all other events"""
    logger.info(f"RECEIVED OTHER EVENT: {type(event).__name__}")
    logger.info(f"Event details: {event}")


def generate_image_with_reference(user_id: str, prompt: str, reference_image_bytes: bytes):
    """Generate image using reference image understanding + user prompt"""
    try:
        print(f"DEBUG: Generating image with reference for prompt: '{prompt}'")
        
        # Step 1: Use Gemini to understand the reference image
        try:
            print("DEBUG: Analyzing reference image with Gemini...")
            vision_response = genai_client.models.generate_content(
                model='gemini-3-flash-preview',
                contents=[
                    types.Part.from_bytes(
                        data=reference_image_bytes,
                        mime_type='image/jpeg'
                    ),
                    "この画像を詳しく説明してください。構図、色調、雰囲気、主要な要素などを含めて。"
                ]
            )
            image_description = vision_response.text
            print(f"DEBUG: Image understanding complete: {image_description[:100]}...")
        except Exception as vision_err:
            print(f"DEBUG: Vision analysis FAILED: {str(vision_err)}")
            raise Exception(f"画像理解エラー: {str(vision_err)}")
        
        # Step 2: Combine understanding with user prompt
        enhanced_prompt = f"""参照画像の説明:
{image_description}

ユーザーの要望:
{prompt}

上記の参照画像の特徴を踏まえつつ、ユーザーの要望を反映した新しい画像を生成してください。"""
        
        print(f"DEBUG: Enhanced prompt created (length: {len(enhanced_prompt)})")
        
        # Step 3: Generate new image with Gemini
        try:
            response = genai_client.models.generate_images(
                model='gemini-3-pro-image-preview',
                prompt=enhanced_prompt,
                config=types.GenerateImagesConfig(number_of_images=1)
            )
            if not response.generated_images:
                raise ValueError("Google AI returned no images")
            image_bytes = response.generated_images[0].image.image_bytes
            print("DEBUG: AI generation SUCCESS")
        except Exception as gen_err:
            print(f"DEBUG: AI Generation FAILED: {str(gen_err)}")
            raise Exception(f"Google AI画像生成エラー: {str(gen_err)}")
        
        # Step 4: Upload to Cloudinary
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
            detailed_err = str(up_err)
            if "api_key" in detailed_err.lower():
                detailed_err += " (CloudinaryのURL設定が初期値のままの可能性があります)"
            raise Exception(f"Cloudinaryアップロードエラー: {detailed_err}")
        
        # Step 5: Send to LINE
        try:
            with ApiClient(line_configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[
                            TextMessage(text=f"✨ 参照画像を元に新しい画像を生成しました！\n\nプロンプト: {prompt}"),
                            ImageMessage(
                                original_content_url=image_url,
                                preview_image_url=image_url
                            )
                        ]
                    )
                )
            print("DEBUG: LINE Push SUCCESS")
            
            # Clear the context after successful generation
            if user_id in user_image_context:
                del user_image_context[user_id]
                print(f"DEBUG: Cleared context for user {user_id}")
                
        except Exception as line_err:
            print(f"DEBUG: LINE Push FAILED: {str(line_err)}")
            raise Exception(f"LINE送信エラー: {str(line_err)}")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Worker Error (with reference): {error_msg}")
        
        # Send error message
        try:
            with ApiClient(line_configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.push_message(
                    PushMessageRequest(
                        to=user_id,
                        messages=[TextMessage(text=f"❌ 参照画像を使った生成中にエラーが発生しました:\n{error_msg}")]
                    )
                )
        except Exception as final_err:
            logger.error(f"Could not send final error: {str(final_err)}")


def generate_and_send_image(user_id: str, prompt: str):
    """Generate image using Google AI and send to user"""
    try:
        print(f"DEBUG: Generating image for prompt: '{prompt}'")
        
        # Step 1: AI Image Generation
        try:
            response = genai_client.models.generate_images(
                model='gemini-3-pro-image-preview',
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
            print(f"DEBUG: Uploading to Cloudinary (URL format check: {'@' in (cloudinary_url or '')})...")
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
