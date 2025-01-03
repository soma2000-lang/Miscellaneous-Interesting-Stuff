# First, install required packages:
# pip install onnxruntime-gpu numpy pillow

import onnxruntime as ort
import numpy as np
from PIL import Image

def setup_onnx_cuda():
    """Setup ONNX Runtime with CUDA provider"""
    # Check available providers
    providers = ort.get_available_providers()
    print(f"Available providers: {providers}")
    
    # Create inference session with CUDA provider
    providers = [
        ('CUDAExecutionProvider', {
            'device_id': 0,
            'cuda_mem_limit': 2 * 1024 * 1024 * 1024,  # 2GB VRAM limit
            'arena_extend_strategy': 'kNextPowerOfTwo',
        }),
        'CPUExecutionProvider'
    ]
    return providers

def load_model(model_path, providers):
    """Load ONNX model with specified providers"""
    try:
        session = ort.InferenceSession(model_path, providers=providers)
        print(f"Model loaded successfully with providers: {session.get_providers()}")
        return session
    except Exception as e:
        print(f"Error loading model: {e}")
        return None

def prepare_input(input_image_path, input_shape):
    """Prepare image input according to model requirements"""
    image = Image.open(input_image_path)
    # Resize image to match model input shape
    image = image.resize((input_shape[2], input_shape[3]))
    # Convert to numpy array and normalize
    input_data = np.array(image).astype(np.float32)
    # Add batch dimension and transpose to NCHW format if needed
    input_data = np.expand_dims(input_data, axis=0)
    if input_data.shape[1] != input_shape[1]:
        input_data = input_data.transpose(0, 3, 1, 2)
    # Normalize pixel values
    input_data = input_data / 255.0
    return input_data

def run_inference(session, input_data):
    """Run inference on prepared input"""
    try:
        # Get input name from model
        input_name = session.get_inputs()[0].name
        # Run inference
        outputs = session.run(None, {input_name: input_data})
        return outputs
    except Exception as e:
        print(f"Error during inference: {e}")
        return None

def main():
    # Setup CUDA providers
    providers = setup_onnx_cuda()
    
    # Model and input parameters
    model_path = "path/to/your/model.onnx"
    input_image_path = "path/to/your/input/image.jpg"
    input_shape = (1, 3, 224, 224)  # Adjust according to your model
    
    # Load model
    session = load_model(model_path, providers)
    if session is None:
        return
    
    # Prepare input
    input_data = prepare_input(input_image_path, input_shape)
    
    # Run inference
    outputs = run_inference(session, input_data)
    
    if outputs is not None:
        print("Inference results:", outputs[0])

if __name__ == "__main__":
    main()
