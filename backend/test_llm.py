import asyncio
import logging

from app.core.config import settings
from app.prompts.optimized_match import build_optimized_match_prompt
from app.services.llm_service import OllamaLLMService

logging.basicConfig(level=logging.INFO)


async def run():
    if not settings.OLLAMA_LIVE_TESTS_ENABLED:
        raise RuntimeError("Set OLLAMA_LIVE_TESTS_ENABLED=true to run the manual live Ollama check.")

    cv_text = """
## RESUME

NITESH H PARMAR
Mobile-8140896081
AT-BAKROL, POST-KOSAMDI
EMAIL-niteshparmar0711@gmail.com

## EXPERIENCE

- I have completed 1-year apprenticeship at GIL LTD, Ankleshwar from 2014 to 2015
- I have 3-year work experience as plant operator with ATUL LTD, Ankleshwar 2015 to 2018.
- I work with UPL-5 as an officer from 2018 to 2021.
- I work with FMC Chimenova form Plant operator, 2021 to 2023.
- Presently I work with SRF LIMITED DAHEJ from Technician, 2023 to tilde date.

## CAREER PROFILE
- Reactor handing, (SSR & GLR)
- ANF - (Agitated Nutsche Filter)
- RVD - (Rotary vacuum dryer)
- Stem Ejector and Water ring vacuum pump
"""

    prompt, *_ = build_optimized_match_prompt(cv_text, [])

    # Just run the optimized match
    print("Running LLM Match via OllamaLLMService...")
    res = await asyncio.to_thread(
        OllamaLLMService.run_optimized_match,
        prompt=prompt,
        prompt_version="test_3.2",
        cache_key="test_cache_key_2",
    )

    print("CANDIDATE PROFILE:")
    if res and res.candidate_profile:
        print(res.candidate_profile.model_dump_json(indent=2))
    else:
        print("FAILED TO EXTRACT")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    finally:
        OllamaLLMService.unload_model(settings.OLLAMA_MODEL)
        OllamaLLMService.close_transport()
