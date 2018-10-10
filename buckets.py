from enum import Enum

# Estimate buckets
class Buckets(Enum):
    UNDER_5K = "<5K"
    FROM_5K_TO_10K = "5K-10K"
    FROM_10K_TO_50K = "10K-50K"
    FROM_50K_TO_100K = "50K-100K"
    FROM_100K_TO_500K = "100K-500K"
    FROM_500K_TO_1M = "500K-1M"
    FROM_1M_TO_5M = "1M-5M"
    FROM_5M_TO_10M = "5M-10M"
    FROM_10M_TO_50M = "10M-50M"
    FROM_50M_TO_100M = "50M-100M"
    FROM_100M_TO_500M = "100M-500M"
    FROM_500M_TO_1B = "500M-1B"
    OVER_1B = "*>* 1B"