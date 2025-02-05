from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import os
import tempfile
import asyncio
from pathlib import Path
import subprocess
import traceback

app = FastAPI()

@app.post("/add-ding/")
async def add_ding_to_video(
    video: UploadFile = File(...),
    volume: float = 0.10  # Default to 10% volume (0.0 to 1.0 scale)
):
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
            content = await video.read()
            temp_input.write(content)
            temp_input.flush()
            
            # Construct FFmpeg command
            # This will:
            # 1. Take input video
            # 2. Take input ding sound
            # 3. Adjust ding volume
            # 4. Mix them together with the ding at the start
            # 5. Output the final video
            cmd = [
                'ffmpeg',
                '-i', temp_input.name,  # Input video
                '-i', '/app/ding.mp3',  # Input ding sound
                '-filter_complex',
                f'[1:a]volume={volume}[ding];[0:a][ding]amix=inputs=2:duration=first[aout]',
                '-map', '0:v',  # Keep original video
                '-map', '[aout]',  # Use mixed audio
                '-c:v', 'copy',  # Copy video codec (no re-encoding)
                '-c:a', 'aac',  # Output audio codec
                '-shortest',  # Cut to shortest input
                temp_output.name
            ]
            
            # Run FFmpeg command
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            
            if process.returncode != 0:
                raise Exception(f"FFmpeg error: {process.stderr}")
            
            # Check if output file exists and has size
            if not os.path.exists(temp_output.name):
                raise Exception("Output file was not created")
            
            if os.path.getsize(temp_output.name) == 0:
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
            # Clean up files
            try:
                os.unlink(temp_input.name)
            except:
                pass
            try:
                os.unlink(temp_output.name)
            except:
                pass
            
            # Raise error
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process video: {str(e)}"
            )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)