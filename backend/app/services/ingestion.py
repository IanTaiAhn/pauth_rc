# MVP implementation
import io

def extract_text(file_bytes: bytes) -> str:
    try:
        text = file_bytes.decode("utf-8")
        return text
    except UnicodeDecodeError:
        return ""

if __name__ == "__main__":
    text_path = r"C:\Users\n0308g\Git_Repos\pauth_rc\backend\app\data\ortho_payer_policy_mocked\ch1_knee.txt"
    
    # Read the file and get bytes
    with open(text_path, 'rb') as f:
        file_bytes = f.read()
    
    extracted_text = extract_text(file_bytes)
    print(extracted_text)