import json
import time
import requests
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

OUTPUT_DIR = "vulnerable_llm/data"
API_URL = "http://localhost:8000/generate"
PROGRESS_FILE = os.path.join(OUTPUT_DIR, "progress.json") 

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("[경고] progress.json 파일이 손상되었습니다. 초기화합니다.")
            return {}
    return {}

def save_progress(positions):
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(positions, f, ensure_ascii=False, indent=2)

file_positions = load_progress()

def query_vulnerable_llm(prompt_text, seed_id=None, bucket_id=None, triggers=None):
    payload = {
        "prompt": prompt_text,
        "seed_id": seed_id,
        "bucket_id": bucket_id,
        "triggers": triggers,   
    }
    headers = {"Content-Type": "application/json"}
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            response = requests.post(API_URL, json=payload, headers=headers, timeout=120)
            response.raise_for_status() 
            return True 
        except requests.exceptions.RequestException as e:
            print(f" API 호출 에러 (시도 {attempt + 1}/{max_retries}): {e}")
        time.sleep(2) 
    return False

def process_new_lines(file_path):
    global file_positions
    new_prompts = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            last_position = file_positions.get(file_path, 0)
            f.seek(last_position)
            
            for line in f:
                line = line.strip()
                if not line: continue
                
                try:
                    data = json.loads(line)
                    prompt_text = data.get('child_text') or data.get('prompt')
                    if prompt_text:
                        new_prompts.append((prompt_text, data))
                except json.JSONDecodeError:
                    print(f"[경고] 올바르지 않은 JSONL 형식: {line}")
            
            new_position = f.tell()
            
    except Exception as e:
        print(f"파일 읽기 에러: {e}")
        return

    if not new_prompts:
        return

    base_name = os.path.basename(file_path)
    print(f"\n[처리 중] '{base_name}'에서 새로운 프롬프트 {len(new_prompts)}개 발견. 평가 시작.")

    for prompt, original_data in new_prompts:
        current_seed_id = original_data.get("seed_id")
        current_bucket_id = original_data.get("bucket_id")
        current_triggers = original_data.get("triggers") 
       
        success = query_vulnerable_llm(
            prompt_text=prompt, 
            seed_id=current_seed_id, 
            bucket_id=current_bucket_id,
            triggers=current_triggers,
        )
        
        if success:
            print(f"  -> 평가 및 로깅 완료 (서버): {prompt[:20]}...")
        else:
            print(f"  -> [실패] 서버 응답 없음: {prompt[:20]}...")
            
        time.sleep(0.5)
        
    file_positions[file_path] = new_position
    save_progress(file_positions)

class MutationFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory: return
        file_path = os.path.normpath(event.src_path)
        if file_path.endswith(".jsonl") and "vuln_results.jsonl" not in file_path: 
            print(f"\n[새 파일 감지 (생성)] '{file_path}'")
            if file_path not in file_positions:
                file_positions[file_path] = 0
                save_progress(file_positions)
            process_new_lines(file_path)

    def on_modified(self, event):
        if event.is_directory: return
        file_path = os.path.normpath(event.src_path)
        if file_path.endswith(".jsonl") and "vuln_results.jsonl" not in file_path: 
            process_new_lines(file_path)

    def on_moved(self, event):
        if event.is_directory: return
        file_path = os.path.normpath(event.dest_path) 
        if file_path.endswith(".jsonl") and "vuln_results.jsonl" not in file_path:
            print(f"\n[새 파일 감지 (이동/복사)] '{file_path}'")
            if file_path not in file_positions:
                file_positions[file_path] = 0
                save_progress(file_positions)
            process_new_lines(file_path)

if __name__ == "__main__":
    watch_dir = "mutation/data"
    
    if not os.path.exists(watch_dir):
        os.makedirs(watch_dir)

    print(f"'{watch_dir}' 폴더 내의 기존 파일들을 초기 스캔합니다...")
    for filename in os.listdir(watch_dir):
        if filename.endswith(".jsonl") and filename != "vuln_results.jsonl":
            existing_file_path = os.path.join(watch_dir, filename)
            
            if existing_file_path not in file_positions:
                file_positions[existing_file_path] = 0
                save_progress(file_positions)
                
            process_new_lines(existing_file_path)
            
    print("기존 파일 확인 완료.\n")

    event_handler = MutationFileHandler()
    observer = Observer()
    observer.schedule(event_handler, watch_dir, recursive=False)
    
    observer.start()
    print(f"'{watch_dir}' 폴더 실시간 감시 대기 중... (서버가 켜져 있는지 확인하세요!)")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n감시를 종료합니다.")
        observer.stop()
        
    observer.join()