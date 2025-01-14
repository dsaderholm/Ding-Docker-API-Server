from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip
import os
import tempfile
import asyncio
from pathlib import Path
import traceback

app = FastAPI()

@app.post("/add-ding/")
async def add_ding_to_video(
    video: UploadFile = File(...),
    volume: float = 0.10  # Default to 30% volume (0.0 to 1.0 scale)
):
    # Validate file type (basic check)
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
        
        # Save uploaded video
        content = await video.read()
        temp_input.write(content)
        temp_input.flush()
        
        try:
            # Debug: Print file paths
            print(f"Input video path: {temp_input.name}")
            print(f"Output video path: {temp_output.name}")
            
            # Check if ding file exists
            ding_path = "/app/ding.mp3"
            if not os.path.exists(ding_path):
                raise FileNotFoundError(f"Ding sound file not found at {ding_path}")
            
            # Load the video and ding sound
            video_clip = VideoFileClip(temp_input.name)
            ding_clip = AudioFileClip(ding_path)
            
            # Adjust the volume of the ding
            ding_clip = ding_clip.volumex(volume)
            
            # Create a composite audio that overlays ding sound with existing audio
            original_audio = video_clip.audio
            if original_audio:
                # If video has audio, overlay ding sound with existing audio
                composite_audio = CompositeAudioClip([
                    original_audio,
                    ding_clip.with_start(0)
                ])
            else:
                # If no original audio, just use ding sound
                composite_audio = ding_clip
            
            # Set the new audio to the video
            final_clip = video_clip.with_audio(composite_audio)
            
            # Write the final video
            final_clip.write_videofile(
                temp_output.name, 
                codec='libx264', 
                audio_codec='aac'
            )
            
            # Close clips to release resources
            final_clip.close()
            video_clip.close()
            ding_clip.close()
            
        except Exception as e:
            # Detailed error logging
            print("Error during video processing:")
            traceback.print_exc()
            
            # Clean up files before raising exception
            try:
                os.unlink(temp_input.name)
            except:
                pass
            
            try:
                os.unlink(temp_output.name)
            except:
                pass
            
            # Raise HTTP exception with detailed error
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to process video: {str(e)}\n{traceback.format_exc()}"
            )
        
        # Create async cleanup function
        async def cleanup_files():
            try:
                # Use asyncio to run file deletion in a thread pool
                await asyncio.get_event_loop().run_in_executor(
                    None, os.unlink, temp_input.name
                )
                await asyncio.get_event_loop().run_in_executor(
                    None, os.unlink, temp_output.name
                )
            except Exception as e:
                print(f"Cleanup error: {str(e)}")
        
        # Properly format filename in Content-Disposition header
        headers = {
            'Content-Type': 'video/mp4',
            'Content-Disposition': f'attachment; filename="{Path(original_filename).name}"'
        }

        response = FileResponse(
            path=temp_output.name,
            headers=headers
        )
        
        response.background = cleanup_files
        return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
