import os
import numpy as np
import pandas as pd

# Define relative paths
raw_path = 'data/raw/delhi_ncr_airbnb_synthetic.csv'
output_path = 'data/processed/delhi_ncr_airbnb_realistic.csv'

# Ensure output directory exists
os.makedirs('data/processed', exist_ok=True)

# 1. Load raw CSV
if not os.path.exists(raw_path):
    raise FileNotFoundError(
        f'Could not find {raw_path}. Make sure it is inside data/raw/'
    )

df = pd.read_csv(raw_path)

# 2. Expanded State & Region Mapping (Including Delhi-NCR, Punjab, and Himachal Pradesh)
state_map = {
    # Delhi Neighborhoods
    'Paharganj': 'Delhi',
    'Lajpat Nagar': 'Delhi',
    'South Extension': 'Delhi',
    'Old Delhi': 'Delhi',
    'Greater Kailash': 'Delhi',
    'Connaught Place': 'Delhi',
    'Janakpuri': 'Delhi',
    'Karol Bagh': 'Delhi',
    'Vasant Kunj': 'Delhi',
    'Hauz Khas': 'Delhi',
    'Dwarka': 'Delhi',
    'Aerocity': 'Delhi',
    'Rajendra Place': 'Delhi',
    'Saket': 'Delhi',
    'Chattarpur': 'Delhi',
    'Mahipalpur': 'Delhi',
    'Defence Colony': 'Delhi',
    'Uttam Nagar': 'Delhi',
    'Vikaspuri': 'Delhi',
    'Mehrauli': 'Delhi',
    'Green Park': 'Delhi',
    
    # Uttar Pradesh
    'Noida Sector 18': 'Uttar Pradesh',
    'Noida Sector 137': 'Uttar Pradesh',
    'Noida Sector 62': 'Uttar Pradesh',
    'Noida Sector 75': 'Uttar Pradesh',
    'Ghaziabad Indirapuram': 'Uttar Pradesh',
    'Ghaziabad Vaishali': 'Uttar Pradesh',
    
    # Haryana
    'Faridabad Sector 15': 'Haryana',
    'Gurgaon Sector 47': 'Haryana',
    'Gurgaon Golf Course Road': 'Haryana',
    'Gurgaon DLF Phase 2': 'Haryana',
    'Gurgaon Cyber City': 'Haryana',
    
    # Punjab (Added for rich regional filter coverage)
    'Amritsar Golden Temple Area': 'Punjab',
    'Ludhiana Civil Lines': 'Punjab',
    'Chandigarh Sector 17': 'Punjab',
    'Jalandhar Cantt': 'Punjab',
    'Patiala Heritage Zone': 'Punjab',
    'Punjab Farm Stay Rural': 'Punjab',
    
    # Himachal Pradesh (Added for mountain & valley coverage)
    'Shimla Mall Road': 'Himachal Pradesh',
    'Manali Old Manali': 'Himachal Pradesh',
    'Dharamshala McLeod Ganj': 'Himachal Pradesh',
    'Kasauli Ridge': 'Himachal Pradesh',
    'Solan Valley': 'Himachal Pradesh',
    'Dalhousie Pine Hills': 'Himachal Pradesh',
}

# Map neighborhoods, and use a flexible fallback for any unmapped or synthetic rows
df['state'] = df['neighbourhood'].map(state_map)
# Fallback distribution for rows that don't match exact dictionary keys
unmapped_mask = df['state'].isna()
if unmapped_mask.any():
    df.loc[unmapped_mask, 'state'] = np.random.choice(
        ['Delhi', 'Uttar Pradesh', 'Haryana', 'Punjab', 'Himachal Pradesh'], 
        size=unmapped_mask.sum(), 
        p=[0.4, 0.2, 0.2, 0.1, 0.1]
    )

# 3. Market Pricing Multipliers by Room Type
multiplier = {
    'Entire home/apt': 1.6,
    'Hotel room': 1.3,
    'Private room': 0.9,
    'Shared room': 0.5,
}

# 4. Realistic Feature Injections
np.random.seed(42)

df['adjusted_price'] = df.apply(
    lambda r: int(r['price'] * multiplier.get(r['room_type'], 1.0)), axis=1
)
df['review_scores_rating'] = np.round(
    np.random.uniform(3.8, 5.0, size=len(df)), 2
)
df['cleanliness_rating'] = np.round(
    np.random.uniform(3.5, 5.0, size=len(df)), 1
)
df['distance_to_metro_km'] = np.round(
    np.random.exponential(scale=1.2, size=len(df)) + 0.2, 2
)
df['amenities_count'] = np.random.randint(5, 25, size=len(df))
df['host_is_superhost'] = np.where(
    (df['review_scores_rating'] >= 4.7) & (df['number_of_reviews'] >= 30),
    't',
    'f',
)
df['instant_bookable'] = np.random.choice(['t', 'f'], size=len(df), p=[0.4, 0.6])

# 5. Save processed CSV
df.to_csv(output_path, index=False)
print(f'Success! Realistic dataset with full North India coverage generated at: {output_path}')