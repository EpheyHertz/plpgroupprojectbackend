# # consumers.py
# import json
# import base64
# import websockets
# import pyaudio
# import asyncio
# from channels.generic.websocket import AsyncWebsocketConsumer
# from django.conf import settings

# # Initialize pyaudio parameters
# FRAMES_PER_BUFFER = 3200
# FORMAT = pyaudio.paInt16
# CHANNELS = 1
# RATE = 16000
# p = pyaudio.PyAudio()

# # Start the recording stream
# stream = p.open(
#     format=FORMAT,
#     channels=CHANNELS,
#     rate=RATE,
#     input=True,
#     frames_per_buffer=FRAMES_PER_BUFFER
# )
# settings.configure()
# # AssemblyAI API details

# URL = "wss://api.assemblyai.com/v2/realtime/ws?sample_rate=16000"

# class TranscriptionConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         # Accept WebSocket connection
#         await self.accept()
#         print("WebSocket connection accepted")

#         # Start sending and receiving transcription
#         asyncio.create_task(self.transcribe_audio())

#     async def disconnect(self, close_code):
#         # Close the WebSocket connection
#         print(f"WebSocket connection closed with code {close_code}")
#         await self.close()

#     async def transcribe_audio(self):
#         print(f'Connecting to AssemblyAI WebSocket at {URL}')
#         async with websockets.connect(
#             URL,
#             extra_headers=(("Authorization", auth_key),),
#             ping_interval=5,
#             ping_timeout=20
#         ) as _ws:
#             await asyncio.sleep(0.1)
#             session_begins = await _ws.recv()  # Get session begins message
#             print(session_begins)
#             print("Session started, streaming audio...")

#             async def send_audio():
#                 while True:
#                     try:
#                         data = stream.read(FRAMES_PER_BUFFER)  # Read audio data from the microphone
#                         encoded_data = base64.b64encode(data).decode("utf-8")  # Encode audio in base64
#                         audio_json = json.dumps({"audio_data": encoded_data})  # Convert to JSON format
#                         await _ws.send(audio_json)  # Send audio data to AssemblyAI
#                     except websockets.exceptions.ConnectionClosedError as e:
#                         print(f"Connection closed: {e}")
#                         break
#                     except Exception as e:
#                         print(f"Error: {e}")
#                         break
#                     await asyncio.sleep(0.01)

#             async def receive_transcription():
#                 while True:
#                     try:
#                         response = await _ws.recv()  # Receive transcribed text from AssemblyAI
#                         result = json.loads(response)
#                         if result.get("message_type") == "FinalTranscript":
#                             transcript_text = result["text"]
#                             print(f"Transcription: {transcript_text}")
#                             # Send the transcription to the frontend WebSocket
#                             await self.send(text_data=json.dumps({"transcription": transcript_text}))
#                     except websockets.exceptions.ConnectionClosedError as e:
#                         print(f"Connection closed: {e}")
#                         break
#                     except Exception as e:
#                         print(f"Error receiving data: {e}")
#                         break

#             # Run send and receive in parallel
#             await asyncio.gather(send_audio(), receive_transcription())
