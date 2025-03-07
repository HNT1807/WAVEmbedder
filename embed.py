import os
import tempfile
from mutagen.wave import WAVE
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TBPM, TKEY, TCOM, TPUB, COMM


def add_riff_metadata(input_wav_path, output_wav_path, metadata_dict):
    def encode_riff_info(tag, value):
        value_bytes = value.encode("utf-8")
        # Pad with null byte if odd length
        if len(value_bytes) % 2 == 1:
            value_bytes += b'\x00'
        size = len(value_bytes)
        return tag.encode("ascii") + size.to_bytes(4, "little") + value_bytes

    # Build RIFF metadata bytes
    metadata_bytes = b""
    if "Track Title" in metadata_dict:
        metadata_bytes += encode_riff_info("INAM", metadata_dict["Track Title"])
    if "Composers" in metadata_dict:
        metadata_bytes += encode_riff_info("IART", metadata_dict["Composers"])
    if "Source Program" in metadata_dict:
        metadata_bytes += encode_riff_info("IALB", metadata_dict["Source Program"])
    comments = []
    if "BPM" in metadata_dict:
        comments.append(f"BPM: {metadata_dict['BPM']}")
    if "Key" in metadata_dict:
        comments.append(f"Key: {metadata_dict['Key']}")
    if "Publishers" in metadata_dict:
        comments.append(f"Publishers: {metadata_dict['Publishers']}")
    if comments:
        comment_str = " | ".join(comments)
        metadata_bytes += encode_riff_info("ICMT", comment_str)

    # Create LIST chunk: "LIST" + (4-byte size) + "INFO" + metadata
    list_chunk_data = b"INFO" + metadata_bytes
    list_chunk_size = len(list_chunk_data)
    list_chunk = b"LIST" + list_chunk_size.to_bytes(4, "little") + list_chunk_data

    # Read the original WAV data.
    with open(input_wav_path, "rb") as f:
        wav_data = f.read()

    # Verify that the file is a valid WAV file.
    if wav_data[0:4] != b"RIFF" or wav_data[8:12] != b"WAVE":
        raise RuntimeError("Not a valid WAV file.")

    # Locate the end of the "fmt " chunk.
    pos = 12
    fmt_end = None
    while pos + 8 <= len(wav_data):
        chunk_id = wav_data[pos:pos + 4]
        chunk_size = int.from_bytes(wav_data[pos + 4:pos + 8], "little")
        if chunk_id == b"fmt ":
            fmt_end = pos + 8 + chunk_size
            break
        pos += 8 + chunk_size
    if fmt_end is None:
        raise RuntimeError("No 'fmt ' chunk found.")

    # Insert the LIST chunk right after the "fmt " chunk.
    new_wav_data = wav_data[:fmt_end] + list_chunk + wav_data[fmt_end:]

    with open(output_wav_path, "wb") as f:
        f.write(new_wav_data)


def add_id3_metadata(wav_path, metadata_dict):
    audio = WAVE(wav_path)
    if not audio.tags:
        audio.add_tags()
    audio.tags.clear()

    if "Track Title" in metadata_dict:
        audio.tags.add(TIT2(encoding=3, text=metadata_dict["Track Title"]))
    if "Composers" in metadata_dict:
        audio.tags.add(TPE1(encoding=3, text=metadata_dict["Composers"]))
    if "Source Program" in metadata_dict:
        audio.tags.add(TALB(encoding=3, text=metadata_dict["Source Program"]))
    if "BPM" in metadata_dict:
        audio.tags.add(TBPM(encoding=3, text=str(metadata_dict["BPM"])))
    if "Key" in metadata_dict:
        audio.tags.add(TKEY(encoding=3, text=metadata_dict["Key"]))

    comments = []
    if "BPM" in metadata_dict:
        comments.append(f"BPM: {metadata_dict['BPM']}")
    if "Key" in metadata_dict:
        comments.append(f"Key: {metadata_dict['Key']}")
    if "Publishers" in metadata_dict:
        comments.append(f"Publishers: {metadata_dict['Publishers']}")
    if comments:
        audio.tags.add(COMM(encoding=3, lang="eng", desc="Description", text=" | ".join(comments)))

    if "Composers" in metadata_dict:
        for composer in metadata_dict["Composers"].split(","):
            audio.tags.add(TCOM(encoding=3, text=composer.strip()))
    if "Publishers" in metadata_dict:
        for publisher in metadata_dict["Publishers"].split(","):
            audio.tags.add(TPUB(encoding=3, text=publisher.strip()))

    audio.save()


def embed_metadata(uploaded_file, metadata_dict, output_filename):
    # Write uploaded file to a temporary WAV file.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_in:
        temp_in.write(uploaded_file.getbuffer())
        temp_in_path = temp_in.name

    # Insert RIFF metadata.
    temp_riff_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    add_riff_metadata(temp_in_path, temp_riff_path, metadata_dict)

    # Copy to a temporary file for adding ID3 metadata.
    temp_final_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    with open(temp_riff_path, "rb") as f_in, open(temp_final_path, "wb") as f_out:
        f_out.write(f_in.read())

    add_id3_metadata(temp_final_path, metadata_dict)

    os.remove(temp_in_path)
    os.remove(temp_riff_path)

    # Move final file to a new temporary directory with the desired output filename.
    output_dir = tempfile.mkdtemp()
    final_output_path = os.path.join(output_dir, output_filename)
    os.rename(temp_final_path, final_output_path)
    return final_output_path

