import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import pytesseract
import tempfile
import os
import math
import numpy as np
from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip
import pyttsx3
import uuid

st.set_page_config(page_title="Texto a video sin API", layout="centered")
st.title("Generador de Video desde Texto o Imagen (Local, Sin API)")
st.write("Sube una imagen con texto o pega texto. Se genera audio y video offline.")

with st.sidebar:
    st.header("Opciones")
    voz_rate = st.slider("Velocidad de voz", 100, 300, 170)
    fondo_color = st.color_picker("Color de fondo", "#FFF6E0")
    texto_color = st.color_picker("Color del texto", "#0B6B3A")
    fontsize = st.slider("Tamaño texto", 28, 80, 40)
    width = st.number_input("Ancho video", 320, 1920, 1280)
    height = st.number_input("Alto video", 240, 1080, 720)
    fps = st.number_input("FPS", 15, 60, 24)

uploaded = st.file_uploader("Subir imagen con texto", type=["jpg","jpeg","png"])
text_input = st.text_area("O pegar texto aquí")

def run_ocr(pil_image):
    try:
        return pytesseract.image_to_string(pil_image)
    except:
        return ""

def synthesize_tts(text, out_path, rate=150):
    engine = pyttsx3.init()
    engine.setProperty('rate', rate)
    for v in engine.getProperty('voices'):
        if 'es' in v.languages or 'Spanish' in v.name:
            engine.setProperty('voice', v.id)
            break
    engine.save_to_file(text, out_path)
    engine.runAndWait()

def chunk_text(text, max_chars=400):
    import re
    text = text.strip()
    if not text:
        return []
    parts = []
    for block in text.split('\n'):
        block = block.strip()
        if not block:
            continue
        sentences = re.split(r'(?<=[.!?])\s+', block)
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if len(s) <= max_chars:
                parts.append(s)
            else:
                for i in range(0, len(s), max_chars):
                    parts.append(s[i:i+max_chars])
    return parts

def render_text_image(text, w, h, bg_color, text_color, font_size):
    img = Image.new('RGB', (w, h), color=bg_color)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except:
        font = ImageFont.load_default()

    margin = 40
    max_width = w - margin*2

    import textwrap
    lines = textwrap.wrap(text, width=math.floor(max_width / (font_size * 0.6)))

    total_h = sum([draw.textsize(line, font=font)[1] for line in lines]) + (len(lines)-1)*10
    y = max((h - total_h)//2, 20)

    for line in lines:
        w_line, h_line = draw.textsize(line, font=font)
        x = (w - w_line)//2
        draw.text((x, y), line, fill=text_color, font=font)
        y += h_line + 10

    return img

if st.button("Generar Video"):
    with st.spinner("Procesando..."):
        final_text = ""

        if text_input.strip():
            final_text = text_input.strip()
        elif uploaded:
            try:
                pil_image = Image.open(uploaded).convert("RGB")
                final_text = run_ocr(pil_image).strip()
                st.text_area("Texto detectado", final_text)
            except:
                st.error("No se pudo leer la imagen.")
                final_text = ""

        if not final_text:
            st.error("No se encontró texto.")
        else:
            chunks = chunk_text(final_text, max_chars=300)
            if not chunks:
                st.error("No hay contenido.")
            else:
                tmpdir = tempfile.mkdtemp()
                audio_path = os.path.join(tmpdir, f"speech_{uuid.uuid4().hex}.mp3")

                synthesize_tts(final_text, audio_path, rate=voz_rate)

                clips = []
                total_chars = sum(len(c) for c in chunks)

                for c in chunks:
                    dur = max(1.0, (len(c)/total_chars) * max(3, len(chunks)*2))
                    img = render_text_image(c, int(width), int(height), fondo_color, texto_color, fontsize)
                    arr = np.array(img)
                    clip = ImageClip(arr).set_duration(dur)
                    clips.append(clip)

                final_clip = concatenate_videoclips(clips, method="compose")

                audio = AudioFileClip(audio_path)

                if abs(audio.duration - final_clip.duration) > 0.5:
                    factor = audio.duration / final_clip.duration
                    new_clips = [c.set_duration(c.duration * factor) for c in clips]
                    final_clip = concatenate_videoclips(new_clips, method="compose")

                final_clip = final_clip.set_audio(audio)

                output_path = os.path.join(tmpdir, f"video_{uuid.uuid4().hex}.mp4")
                final_clip.write_videofile(output_path, fps=int(fps), codec="libx264", audio_codec="aac")

                st.success("Video generado")
                st.video(output_path)
                with open(output_path, "rb") as f:
                    st.download_button("Descargar MP4", f, "video.mp4", "video/mp4")


