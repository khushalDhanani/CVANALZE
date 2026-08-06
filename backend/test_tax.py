from app.services.dynamic_taxonomy_service import DynamicTaxonomyService

def main():
    res = DynamicTaxonomyService.resolve_candidate_role_and_domain(
        role_or_summary="flutter developer dart",
        skills="flutter dart mobile"
    )
    print(res)

if __name__ == "__main__":
    main()
