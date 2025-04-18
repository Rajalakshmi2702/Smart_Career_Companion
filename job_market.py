import requests

# Replace with your actual JSearch API key
API_KEY = "a871fd0f5amsh560c22aa70298e8p151884jsn5f4ebc336755"
BASE_URL = "https://jsearch.p.rapidapi.com/search"

headers = {
    "X-RapidAPI-Key": API_KEY,
    "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
}

def get_trending_jobs(country=None, domain=None):
    # Default query can be changed or made dynamic
    query = "software engineer"
    params = {
        "query": query,
        "num_pages": 1
    }
    if country:
        params["country"] = country
    if domain:
        params["domain"] = domain
    response = requests.get(BASE_URL, headers=headers, params=params)
    if response.status_code == 200:
        return response.json().get("data", [])
    return []

def get_in_demand_skills():
    job_data = get_trending_jobs()  # You can modify to pass same filters if needed.
    skills_count = {}
    
    if not job_data:
        return [("No skills data available", 0)]

    for job in job_data:
        skills = job.get("job_required_skills")
        if not skills and "job_description" in job:
            description = job["job_description"]
            # Simple extraction: split description into words; use real NLP in production!
            words = description.split()
            skills = [word.strip(".,").lower() for word in words if len(word) > 4]
        
        if skills:
            for skill in skills:
                skills_count[skill] = skills_count.get(skill, 0) + 1

    if not skills_count:
        return [("No skills data available", 0)]
    
    sorted_skills = sorted(skills_count.items(), key=lambda x: x[1], reverse=True)
    return sorted_skills[:10]

def get_salary_benchmarks():
    job_data = get_trending_jobs()
    salaries = []

    if not job_data:
        return {"error": "No salary data available"}

    for job in job_data:
        min_sal = job.get("job_min_salary")
        max_sal = job.get("job_max_salary")
        if min_sal is not None and max_sal is not None:
            try:
                min_sal = float(min_sal)
                max_sal = float(max_sal)
                salaries.append((min_sal, max_sal))
            except (ValueError, TypeError):
                continue

    if not salaries:
        return {"error": "No salary data available"}

    avg_salary = sum([(s[0] + s[1]) / 2 for s in salaries]) / len(salaries)
    return {"average_salary": avg_salary}

# For testing purposes
if __name__ == "__main__":
    print("Trending Jobs:", get_trending_jobs())
    print("In-Demand Skills:", get_in_demand_skills())
    print("Salary Benchmarks:", get_salary_benchmarks())
