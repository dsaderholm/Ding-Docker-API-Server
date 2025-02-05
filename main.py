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
    """Run FFmpeg command and return detailed output"""
    print(f"Running FFmpeg command: {' '.join(cmd)}")
    try:
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        print(f"Return code: {process.returncode}")
        print(f"stdout: {process.stdout}")
        print(f"stderr: {process.stderr}")
        return process
    except Exception as e:
        print(f"Exception running FFmpeg: {str(e)}")
        raise

@app.post("/add-ding/")
async def add_ding_to_video(
    video: UploadFile = File(...),
    volume: float = 0.10  # Default to 10% volume (0.0 to 1.0 scale)
):
    print(f"Processing new request. Video filename: {video.filename}, Volume: {volume}")
    
    # Validate file type
    if not video.filename.endswith(('.mp4', '.avi', '.mov')):
        raise HTTPException(status_code=400, detail="Unsupported file format")
    
    # Validate volume parameter
    if not 0 <= volume <= 1:
        raise HTTPException(status_code=400, detail="Volume must be between 0.0 and 1.0")
    
    # Get original filename and extension
    original_filename = video.filename
    file_extension = os.path.splitext(original_filename)[1]
    
    # Create temporary files for processing
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_input, \
         tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_output:
        
        try:
            # Save uploaded video
            print("Reading uploaded content...")
            content = await video.read()
            temp_input.write(content)
            temp_input.flush()
            print(f"Saved input video to: {temp_input.name} (size: {len(content)} bytes)")
            
            # Verify input file exists
            if not os.path.exists('/app/ding.mp3'):
                print("Checking ding.mp3 location:")
                print(f"Current directory contents: {os.listdir('/app')}")
                raise Exception("ding.mp3 not found in /app directory")
            
            print(f"Input file size: {os.path.getsize(temp_input.name)}")
            print(f"Ding file size: {os.path.getsize('/app/ding.mp3')}")
            
            # Construct FFmpeg command - added -y flag to force overwrite
            cmd = [
                'ffmpeg',
                '-y',  # Force overwrite output file
                '-i', temp_input.name,
                '-i', '/app/ding.mp3',
                '-filter_complex',
                f'[1:a]volume={volume}[ding];[0:a][ding]amix=inputs=2:duration=first[aout]',
                '-map', '0:v',
                '-map', '[aout]',
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-shortest',
                temp_output.name
            ]
            
            # Run FFmpeg
            process = run_ffmpeg_command(cmd)
            
            if process.returncode != 0:
                raise Exception(f"FFmpeg failed with error: {process.stderr}")
            
            output_size = os.path.getsize(temp_output.name)
            print(f"Output file size: {output_size}")
            
            if output_size == 0:
                raise Exception("Output file is empty")
            
            # Set up response headers
            headers = {
                'Content-Type': 'video/mp4',
                'Content-Disposition': f'attachment; filename="{Path(original_filename).name}"'
            }
            
            # Create response
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
            
            # Raise error
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process video: {str(e)}\n{traceback.format_exc()}"
            )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)