import asyncio
from pathlib import Path
from app.services.cv_service import process_cv_file

async def main():
    file_path = Path("uploads/alex_johnson_cv.docx")
    content = file_path.read_bytes()
    filename = file_path.name
    print(f"Processing {filename}...")
    
    result = await process_cv_file(
        filename=filename,
        content=content,
        force_reprocess=True
    )
    
    print("Result status:", result.get("status"))
    print("Result file path:", result.get("result_file_path"))
    
    # Check if .md file exists
    md_path = Path("uploads/results/cv_alex_johnson_cv.md")
    if md_path.exists():
        print(f"MD file generated successfully at {md_path}")
        print(f"MD file size: {md_path.stat().st_size} bytes")
    else:
        print(f"MD file NOT found at {md_path}")

if __name__ == "__main__":
    asyncio.run(main())
