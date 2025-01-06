from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip
import os
import tempfile
import asyncio
from pathlib import Path

app = FastAPI()

@app.post("/add-ding/")
async def add_ding_to_video(
    video: UploadFile = File(...),
    ding_duration: float = 1.0
):
    # Validate file type (basic check)
    if not video.filename.endswith(('.mp4', '.avi', '.mov')):
        raise HTTPException(status_code=400, detail="Unsupported file format")
    
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
            # Load the video and ding sound
            video_clip = VideoFileClip(temp_input.name)
            ding_clip = AudioFileClip("/app/ding.mp3")
            
            # Trim ding to specified duration
            ding_clip = ding_clip.subclip(0, min(ding_duration, ding_clip.duration))
            
            # Create a composite audio that combines ding and original audio
            original_audio = video_clip.audio
            if original_audio:
                # If video has audio, mix ding sound with existing audio
                composite_audio = CompositeAudioClip([
                    ding_clip.set_start(0),
                    original_audio.set_start(ding_clip.duration)
                ])
            else:
                # If no original audio, just use ding sound
                composite_audio = ding_clip
            
            # Set the new audio to the video
            final_clip = video_clip.set_audio(composite_audio)
            
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
            # Clean up files before raising exception
            os.unlink(temp_input.name)
            os.unlink(temp_output.name)
            raise HTTPException(status_code=500, detail=f"Failed to process video: {str(e)}")
        
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
