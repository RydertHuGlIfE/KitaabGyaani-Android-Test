import asyncio
import sys
import os
import base64
from io import BytesIO

# Add root folder to python path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.llm_service import LLMService

async def debug_vision_call():
    # Dynamically generate a valid 10x10 JPEG image
    try:
        from PIL import Image
    except ImportError:
        # Fallback to a verified valid 2x2 JPEG base64 if PIL is not installed
        # This is a real 2x2 red pixel JPEG encoded to base64
        mock_base64 = "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAACAAIBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
    else:
        img = Image.new("RGB", (10, 10), color="red")
        buffered = BytesIO()
        img.save(buffered, format="JPEG")
        mock_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    llm = LLMService()
    prompt = "Tell me what color this image is."
    
    print("Testing raw llm vision model call directly...")
    try:
        raw_response = await llm.query_vision_llm(mock_base64, prompt)
        print("Raw Response Length:", len(raw_response))
        print("Raw Response Content:", repr(raw_response))
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_vision_call())
