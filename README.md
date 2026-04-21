# NAICS Lookup API

## Overview
A simple API to query NAICS codes and descriptions.

Data source is the "Six Digit NACIS" tab on the official [2022 NAICS Codes spreadsheet](https://www.naics.com/wp-content/uploads/2022/05/2022-NAICS-Codes-listed-numerically-2-Digit-through-6-Digit.xlsx).

## Endpoints

### /search
Search for NAICS codes. Based on search query, results are scored by summing their points in the table below, and sorted in descending order. Description of NAICS code can be included or excluded. Returns up to `limit` results.

| Parameter | Description | Points |
|---|---|---|
| TITLE_EXACT_WEIGHT | Query phrase found verbatim in title | 100 |
| DESC_EXACT_WEIGHT | Query phrase found verbatim in description | 60 |
| TITLE_WORD_WEIGHT | Each query word found in title | 15 |
| DESC_WORD_WEIGHT | Each query word found in description| 5 |
| FUZZY_TITLE_WEIGHT | rapidfuzz partial_ratio on title (scaled 0-40) | 0.4 |
FUZZY_DESC_WEIGHT | rapidfuzz partial_ratio on description (scaled 0-15) | 0.15 |

### /code
Returns the title and description for an exact 6-digit NAICS code.

### /health
Returns API status and number of records loaded.

## To test locally:
1. cd to this dir
2. Open terminal
3. Run "python -m uvicorn main:app --reload"
4. Test from Postman or Swagger page at http://127.0.0.1:8000/docs