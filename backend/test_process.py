from app.services.cv_service import process_cv_file
import asyncio
from pathlib import Path

async def main():
    file_path = "uploads/cv_gptsuifgr321345678o9p_c369770edae6dbd27123d2ea68cc20cf6329535022a48c74850c0e20df910fd6.pdf"
    content = Path(file_path).read_bytes()
    filename = Path(file_path).name

    result = await process_cv_file(filename=filename, content=content, force_reprocess=True)
    match_analysis = result.get("match_analysis", {})
    print("BEST VACANCIES:", match_analysis.get("best_vacancies"))
    print("DEPT:", match_analysis.get("primary_department"))
    print("ROLE FIT:", match_analysis.get("role_department_fit"))

if __name__ == "__main__":
    asyncio.run(main())
