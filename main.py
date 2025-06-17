from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import os
import tempfile
import asyncio
from pathlib import Path
import subprocess
import traceback
import time
import threading

# Import Intel Arc GPU initialization
try:
    from intel_gpu_init import initialize_intel_arc_gpu
except ImportError:
    def initialize_intel_arc_gpu():
        """Intel Arc GPU initialization placeholder"""
        pass

app = FastAPI()

# Global lock to prevent concurrent processing
processing_lock = threading.Lock()
processing_in_progress = False

# Initialize Intel Arc GPU on startup
initialize_intel_arc_gpu()

def run_ffmpeg_command(cmd):
    """Run FFmpeg command with Intel Arc GPU acceleration and return detailed output"""
    print(f"Running FFmpeg command: {' '.join(cmd)}")
    try:
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        print(f"Return code: {process.returncode}")
        if process.stdout:
            print(f"stdout: {process.stdout}")
        if process.stderr:
            print(f"stderr: {process.stderr}")
        return process
    except Exception as e:
        print(f"Exception running FFmpeg: {str(e)}")
        raise

def try_intel_arc_encoding(input_path: str, output_path: str, ding_path: str, volume: float, max_retries: int = 3) -> bool:
    """Try Intel Arc hardware encoding with multiple fallback methods."""
    for attempt in range(max_retries):
        try:
            print(f"🚀 Attempting Intel Arc hardware encoding (attempt {attempt + 1})...")
            
            # Method 1: Intel Arc-specific QSV (requires proper drivers)
            try:
                print("🎯 Using Intel Arc QSV (requires updated drivers)...")
                
                cmd = [
                    'ffmpeg',
                    '-y',  # Force overwrite
                    '-threads', '16',
                    # QSV-specific initialization
                    '-init_hw_device', 'qsv=hw',
                    '-filter_hw_device', 'hw',
                    '-i', input_path,
                    '-i', ding_path,
                    '-filter_complex',
                    f'[1:a]volume={volume}[ding];[0:a][ding]amix=inputs=2:duration=first[aout];[0:v]format=qsv,hwupload=extra_hw_frames=64[v]',
                    '-map', '[v]',
                    '-map', '[aout]',
                    # Intel Arc QuickSync encoding
                    '-c:v', 'h264_qsv',
                    '-preset', 'medium',
                    '-global_quality', '23',
                    '-look_ahead', '1',
                    '-c:a', 'aac',
                    '-shortest',
                    output_path
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                
                if result.returncode == 0:
                    print("✅ Intel Arc QSV encoding successful!")
                    return True
                else:
                    print(f"⚠️ QSV failed - likely driver issue")
                    raise subprocess.CalledProcessError(result.returncode, cmd, result.stderr)
                    
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                print(f"⚠️ QSV failed, trying VA-API...")
                
                # Method 2: VA-API with software overlay (more compatible)
                try:
                    print("🔄 Using VA-API encoding...")
                    
                    cmd = [
                        'ffmpeg',
                        '-y',  # Force overwrite
                        '-threads', '16',
                        '-i', input_path,
                        '-i', ding_path,
                        '-filter_complex',
                        f'[1:a]volume={volume}[ding];[0:a][ding]amix=inputs=2:duration=first[aout];[0:v]format=nv12,hwupload[v]',
                        '-map', '[v]',
                        '-map', '[aout]',
                        '-c:v', 'h264_vaapi',
                        '-vaapi_device', '/dev/dri/renderD128',
                        '-qp', '23',
                        '-c:a', 'aac',
                        '-shortest',
                        output_path
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                    
                    if result.returncode == 0:
                        print("✅ Intel Arc VA-API encoding successful!")
                        return True
                    else:
                        print(f"⚠️ VA-API failed: {result.stderr[-200:] if result.stderr else 'Unknown error'}")
                        raise subprocess.CalledProcessError(result.returncode, cmd, result.stderr)
                        
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                    print(f"⚠️ VA-API also failed, trying basic encoding...")
                    
                    # Method 3: Basic hardware acceleration
                    try:
                        print("🔄 Trying basic hardware acceleration...")
                        
                        cmd = [
                            'ffmpeg',
                            '-y',  # Force overwrite
                            '-threads', '16',
                            '-hwaccel', 'vaapi',
                            '-hwaccel_device', '/dev/dri/renderD128',
                            '-i', input_path,
                            '-i', ding_path,
                            '-filter_complex',
                            f'[1:a]volume={volume}[ding];[0:a][ding]amix=inputs=2:duration=first[aout]',
                            '-map', '0:v',
                            '-map', '[aout]',
                            '-c:v', 'h264_vaapi',
                            '-qp', '23',
                            '-c:a', 'aac',
                            '-shortest',
                            output_path
                        ]
                        
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                        
                        if result.returncode == 0:
                            print("✅ Basic hardware acceleration successful!")
                            return True
                        else:
                            print("⚠️ Basic hardware acceleration failed")
                            raise subprocess.CalledProcessError(result.returncode, cmd, result.stderr)
                            
                    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
                        print(f"⚠️ All Intel Arc methods failed, falling back to software...")
                        raise e
            
        except Exception as e:
            print(f"❌ Intel Arc encoding attempt {attempt + 1} failed:")
            if hasattr(e, 'stderr') and e.stderr:
                error_msg = e.stderr if isinstance(e.stderr, str) else e.stderr.decode("utf8")
                print("Error:", error_msg[-200:])  # Show last 200 chars
                
                # Specific Intel Arc troubleshooting
                if "qsv" in error_msg.lower() or "mfx" in error_msg.lower():
                    print("💡 QSV failed - Intel drivers may need updating")
                elif "vaapi" in error_msg.lower():
                    print("💡 VAAPI failed - trying software fallback")
                elif "device" in error_msg.lower():
                    print("💡 GPU device issue - check Docker device mapping")
            else:
                print(f"Error: {str(e)}")
            
            # Don't retry on the last attempt - just fail to software
            if attempt == max_retries - 1:
                print(f"❌ All Intel Arc attempts failed, using software encoding...")
                break
            
            print(f"🔄 Retrying... ({attempt + 1}/{max_retries})")
            time.sleep(2)
    
    return False

def check_intel_arc_support():
    """Enhanced Intel Arc GPU availability check with multiple fallback methods"""
    try:
        # Run vainfo to check GPU hardware acceleration availability
        process = subprocess.run(['vainfo', '--display', 'drm', '--device', '/dev/dri/renderD128'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True,
                               timeout=10)
        
        if process.returncode == 0:
            gpu_info = process.stdout
            if 'Intel' in gpu_info:
                if 'H264' in gpu_info:
                    print("✅ Intel Arc GPU hardware acceleration available")
                    if 'iHD driver' in gpu_info:
                        print("✅ Using Intel iHD driver for optimal Arc performance")
                    return True
                else:
                    print("⚠️ Intel GPU found but H264 support limited")
                    return False
            else:
                print("⚠️ Non-Intel GPU detected")
                return False
        else:
            print("⚠️ Intel GPU hardware acceleration not available")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        print(f"⚠️ GPU check failed: {str(e)}")
        return False

@app.get("/status")
async def get_status():
    """Get current processing status"""
    return {
        "processing_in_progress": processing_in_progress,
        "service": "Ding Audio Processor API"
    }

@app.post("/add-ding/")
async def add_ding_to_video(
    video: UploadFile = File(...),
    volume: float = 0.10  # Default to 10% volume (0.0 to 1.0 scale)
):
    global processing_in_progress
    
    # Check if processing is already in progress
    with processing_lock:
        if processing_in_progress:
            raise HTTPException(
                status_code=429,
                detail="Video processing already in progress. Please wait."
            )
        processing_in_progress = True
    
    try:
        # Validate file type
        if not video.filename.lower().endswith(('.mp4', '.avi', '.mov')):
            raise HTTPException(
                status_code=400, 
                detail="Unsupported file format. Only .mp4, .avi, and .mov files are supported."
            )
        
        # Validate volume parameter
        if not 0 <= volume <= 1:
            raise HTTPException(
                status_code=400, 
                detail="Volume must be between 0.0 and 1.0"
            )
        
        print(f"Processing request for file: {video.filename}")
        
        # Create temporary files for processing
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_input, \
             tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_output:
            
            try:
                # Read file in chunks to handle large files
                print("Reading uploaded file...")
                with open(temp_input.name, 'wb') as buffer:
                    while content := await video.read(1024 * 1024):  # Read 1MB at a time
                        buffer.write(content)
                
                file_size = os.path.getsize(temp_input.name)
                print(f"File saved. Size: {file_size} bytes")
                
                if file_size < 1024:  # Less than 1KB
                    raise HTTPException(
                        status_code=400,
                        detail="Uploaded file is too small to be a valid video file"
                    )
                
                # Verify the video file is valid
                probe_cmd = [
                    'ffprobe',
                    '-v', 'error',
                    '-select_streams', 'v:0',
                    '-show_entries', 'stream=width,height,duration',
                    '-of', 'json',
                    temp_input.name
                ]
                
                probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
                if probe_result.returncode != 0:
                    raise HTTPException(
                        status_code=400,
                        detail="The uploaded file is not a valid video file"
                    )
                
                # Check if ding file exists and is valid
                ding_path = "/app/ding.mp3"
                if not os.path.exists(ding_path):
                    raise HTTPException(
                        status_code=500,
                        detail="Ding sound file not found"
                    )
                
                ding_size = os.path.getsize(ding_path)
                if ding_size == 0:
                    raise HTTPException(
                        status_code=500,
                        detail="Ding sound file is empty"
                    )
                
                print(f"Input video path: {temp_input.name}")
                print(f"Output video path: {temp_output.name}")
                print(f"Ding file size: {ding_size} bytes")
                
                # Check Intel Arc GPU support
                use_gpu = check_intel_arc_support()
                
                # Try Intel Arc hardware encoding first
                if use_gpu:
                    success = try_intel_arc_encoding(temp_input.name, temp_output.name, ding_path, volume)
                    if success:
                        print("✅ Intel Arc hardware encoding completed successfully")
                    else:
                        print("⚠️ Intel Arc encoding failed, falling back to software")
                        use_gpu = False
                
                # Software fallback if Intel Arc failed or not available
                if not use_gpu:
                    print("💻 Using guaranteed software encoding...")
                    cmd = [
                        'ffmpeg',
                        '-y',  # Force overwrite
                        '-threads', '16',
                        '-i', temp_input.name,
                        '-i', ding_path,
                        '-filter_complex',
                        f'[1:a]volume={volume}[ding];[0:a][ding]amix=inputs=2:duration=first[aout]',
                        '-map', '0:v',
                        '-map', '[aout]',
                        '-c:v', 'libx264',
                        '-preset', 'medium',
                        '-crf', '23',
                        '-tune', 'fastdecode',
                        '-c:a', 'aac',
                        '-shortest',
                        temp_output.name
                    ]
                    
                    # Run FFmpeg
                    process = run_ffmpeg_command(cmd)
                    
                    if process.returncode != 0:
                        raise Exception(f"Software FFmpeg failed: {process.stderr}")
                
                # Verify output file
                if not os.path.exists(temp_output.name):
                    raise Exception("Output file was not created")
                
                output_size = os.path.getsize(temp_output.name)
                if output_size == 0:
                    raise Exception("Output file is empty")
                
                print(f"Processing complete. Output size: {output_size} bytes")
                
                # Prepare response
                headers = {
                    'Content-Type': 'video/mp4',
                    'Content-Disposition': f'attachment; filename="{Path(video.filename).stem}_with_ding.mp4"'
                }
                
                response = FileResponse(
                    path=temp_output.name,
                    headers=headers
                )
                
                # Set up cleanup
                async def cleanup_files():
                    try:
                        await asyncio.get_event_loop().run_in_executor(None, os.unlink, temp_input.name)
                        await asyncio.get_event_loop().run_in_executor(None, os.unlink, temp_output.name)
                    except Exception as e:
                        print(f"Cleanup error: {str(e)}")
                
                response.background = cleanup_files
                return response
                
            except Exception as e:
                print("Error occurred:")
                traceback.print_exc()
                
                # Clean up files
                try:
                    os.unlink(temp_input.name)
                    print(f"Cleaned up input file: {temp_input.name}")
                except Exception as cleanup_error:
                    print(f"Error cleaning up input file: {str(cleanup_error)}")
                
                try:
                    os.unlink(temp_output.name)
                    print(f"Cleaned up output file: {temp_output.name}")
                except Exception as cleanup_error:
                    print(f"Error cleaning up output file: {str(cleanup_error)}")
                
                # Return appropriate error
                if isinstance(e, HTTPException):
                    raise e
                raise HTTPException(
                    status_code=500,
                    detail=str(e)
                )
    
    finally:
        # Always reset the processing flag
        with processing_lock:
            processing_in_progress = False

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
