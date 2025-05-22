from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import os
import tempfile
import asyncio
from pathlib import Path
import subprocess
import traceback

app = FastAPI()

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

def check_intel_arc_support():
    """Check if Intel Arc GPU hardware acceleration is available"""
    try:
        # Run vainfo to check GPU hardware acceleration availability
        process = subprocess.run(['vainfo', '--display', 'drm', '--device', '/dev/dri/renderD128'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True,
                               timeout=10)
        
        if process.returncode == 0:
            gpu_info = process.stdout
            if 'Intel' in gpu_info and 'H264' in gpu_info:
                print("✅ Intel Arc GPU hardware acceleration available")
                return True
            else:
                print("⚠️ Intel GPU found but limited codec support")
                return False
        else:
            print("⚠️ Intel GPU hardware acceleration not available")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        print(f"⚠️ GPU check failed: {str(e)}")
        return False

@app.post("/add-ding/")
async def add_ding_to_video(
    video: UploadFile = File(...),
    volume: float = 0.10  # Default to 10% volume (0.0 to 1.0 scale)
):
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
            
            # Construct FFmpeg command with Intel Arc optimization
            if use_gpu:
                print("🚀 Using Intel Arc GPU acceleration for audio mixing")
                cmd = [
                    'ffmpeg',
                    '-y',  # Force overwrite
                    # Intel Arc hardware decoding
                    '-hwaccel', 'vaapi',
                    '-hwaccel_device', '/dev/dri/renderD128',
                    '-i', temp_input.name,
                    '-i', ding_path,
                    '-filter_complex',
                    f'[1:a]volume={volume}[ding];[0:a][ding]amix=inputs=2:duration=first[aout]',
                    '-map', '0:v',
                    '-map', '[aout]',
                    # Intel Arc hardware encoding
                    '-c:v', 'h264_vaapi',
                    '-profile:v', 'high',
                    '-qp', '23',
                    '-c:a', 'aac',
                    '-shortest',
                    temp_output.name
                ]
            else:
                print("💻 Using CPU processing for audio mixing")
                cmd = [
                    'ffmpeg',
                    '-y',  # Force overwrite
                    '-i', temp_input.name,
                    '-i', ding_path,
                    '-filter_complex',
                    f'[1:a]volume={volume}[ding];[0:a][ding]amix=inputs=2:duration=first[aout]',
                    '-map', '0:v',
                    '-map', '[aout]',
                    '-c:v', 'libx264',
                    '-preset', 'medium',
                    '-crf', '23',
                    '-c:a', 'aac',
                    '-shortest',
                    temp_output.name
                ]
            
            # Run FFmpeg
            process = run_ffmpeg_command(cmd)
            
            if process.returncode != 0:
                raise Exception(f"FFmpeg failed: {process.stderr}")
            
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)