
import numpy as np
import time
import os

# Try NLTK VADER first (lightweight, works on all platforms)
try:
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
    VADER_AVAILABLE = True
except ImportError:
    VADER_AVAILABLE = False

# FinBERT fallback (may crash on Mac - only load if explicitly requested)
TRANSFORMERS_AVAILABLE = False
ENABLE_FINBERT = os.getenv('ENABLE_FINBERT', 'false').lower() == 'true'
if ENABLE_FINBERT:
    try:
        import torch
        import torch.nn.functional as F
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        TRANSFORMERS_AVAILABLE = True
    except ImportError:
        pass

# --- Signal 1: Multi-Level Order Book Imbalance (OBI) ---
def calculate_multilevel_obi(order_book_snapshot, levels=5, decay_rate=0.5):
    """
    Calculates Multi-level Order Book Imbalance (OBI) with exponential decay.
    
    Theoretical Basis: DeepLOB implies deeper liquidity supports price, but 
    impact decays with distance from mid-price.
    
    Args:
        order_book_snapshot (dict): Dictionary containing lists of [price, size] 
                                    for 'bids' and 'asks'. 
                                    e.g., {'bids': [[100, 1.5], [99, 2.0]...], 'asks':...}
        levels (int): Number of depth levels to consider (e.g., 5, 10, 20).
        decay_rate (float): Weight decay factor for deeper levels (0 < decay <= 1).
                            A lower decay_rate emphasizes top-of-book more heavily.
        
    Returns:
        float: OBI score between -1.0 (Strong Sell pressure) and +1.0 (Strong Buy pressure).
    """
    # Defensive check
    if not order_book_snapshot or 'bids' not in order_book_snapshot or 'asks' not in order_book_snapshot:
        return 0.0

    # Ensure we have enough levels
    # Convert to standard list if not already
    bids_raw = order_book_snapshot['bids']
    asks_raw = order_book_snapshot['asks']
    
    if not bids_raw or not asks_raw:
        return 0.0

    bids = np.array(bids_raw[:levels])
    asks = np.array(asks_raw[:levels])
    
    # If fewer levels than requested, adjust
    current_levels = min(len(bids), len(asks))
    if current_levels == 0:
        return 0.0
        
    bids = bids[:current_levels]
    asks = asks[:current_levels]
    
    # Extract volumes (index 1 in [price, volume])
    bid_volumes = bids[:, 1]
    ask_volumes = asks[:, 1]
    
    # Generate weights: [1.0, decay, decay^2,...] 
    weights = np.array([decay_rate**i for i in range(current_levels)])
    
    # Calculate weighted sums of liquidity
    weighted_bid_vol = np.sum(bid_volumes * weights)
    weighted_ask_vol = np.sum(ask_volumes * weights)
    
    # Calculate Imbalance Ratio
    total_weighted_vol = weighted_bid_vol + weighted_ask_vol
    
    if total_weighted_vol == 0:
        return 0.0
        
    # OBI Formula: (Bid - Ask) / (Bid + Ask)
    obi = (weighted_bid_vol - weighted_ask_vol) / total_weighted_vol
    
    return float(obi)


# --- Signal 2: Weighted Micro-price (Stoikov Approximation) ---
def calculate_weighted_microprice(best_bid_price, best_bid_vol, best_ask_price, best_ask_vol):
    """
    Calculates the Weighted Micro-price (Naive Stoikov approximation).
    
    Theoretical Basis: Stoikov (2018) & Gatheral (2009). Adjusts the mid-price
    based on the imbalance at the top of the book. 
    
    Args:
        best_bid_price (float): Price of the best bid.
        best_bid_vol (float): Volume of the best bid.
        best_ask_price (float): Price of the best ask.
        best_ask_vol (float): Volume of the best ask.
        
    Returns:
        float: The theoretical micro-price.
    """
    total_vol = best_bid_vol + best_ask_vol
    
    # Handle zero volume edge case
    if total_vol == 0:
        return (best_bid_price + best_ask_price) / 2 # Revert to Standard Mid-price
        
    # Imbalance factor I (0 to 1) representing Bid dominance
    # I = Vb / (Va + Vb)
    imbalance = best_bid_vol / total_vol
    
    # Weighted Micro-price formula:
    # P_micro = I * P_ask + (1 - I) * P_bid
    # Logic: High Bid volume (I -> 1) pushes price toward Ask.
    micro_price = (imbalance * best_ask_price) + ((1 - imbalance) * best_bid_price)
    
    return float(micro_price)

def get_microprice_divergence_signal(current_mid, micro_price, threshold_bps=5.0):
    """
    Generates a signal if Micro-price diverges significantly from Mid-price.
    """
    if current_mid == 0: return 0
    
    # Calculate divergence in Basis Points (bps)
    divergence_bps = ((micro_price - current_mid) / current_mid) * 10000
    
    if divergence_bps > threshold_bps:
        return 1  # Buy: Fair value is significantly higher than mid
    elif divergence_bps < -threshold_bps:
        return -1 # Sell: Fair value is significantly lower than mid
    else:
        return 0  # No Signal (Noise)


# --- Signal 3: Sentiment Scoring (VADER or FinBERT) ---
class SentimentSignalGenerator:
    def __init__(self, model_name="ProsusAI/finbert"):
        """
        Initializes sentiment analysis.
        Uses VADER by default (lightweight, no crashes).
        Only uses FinBERT if ENABLE_FINBERT=true in .env.
        """
        self.enabled = False
        self.use_vader = False
        self.use_finbert = False
        
        # Check environment
        enable_env = os.getenv('ENABLE_SEMANTIC_ALPHA', 'false').lower() == 'true'
        
        if not enable_env:
            print("Sentiment disabled. Set ENABLE_SEMANTIC_ALPHA=true to enable.")
            return
        
        # Try VADER first (safe, works everywhere)
        if VADER_AVAILABLE:
            try:
                self.vader = SentimentIntensityAnalyzer()
                self.use_vader = True
                self.enabled = True
                print("Sentiment: VADER loaded successfully (lightweight, CPU-safe).")
            except Exception as e:
                print(f"Failed to load VADER: {e}")
        
        # Only try FinBERT if explicitly requested AND VADER failed
        if not self.enabled and TRANSFORMERS_AVAILABLE and ENABLE_FINBERT:
            print(f"Loading {model_name}...")
            try:
                self.device = "cpu"
                os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
                self.model = self.model.to(self.device)
                self.model.eval()
                self.use_finbert = True
                self.enabled = True
                print(f"Sentiment: FinBERT loaded (device: {self.device}).")
            except Exception as e:
                print(f"Failed to load FinBERT: {e}")
        
        if not self.enabled:
            print("Sentiment: No engine available.")

    def get_sentiment_score(self, text_input):
        """
        Calculates a scalar sentiment score (-1 to 1) from text.
        Uses VADER or FinBERT depending on what's available.
        """
        if not self.enabled or not text_input:
            return 0.0

        try:
            # VADER (primary - lightweight)
            if self.use_vader:
                scores = self.vader.polarity_scores(text_input)
                # VADER's compound score is already -1 to 1
                return float(scores['compound'])
            
            # FinBERT (fallback - heavyweight)
            elif self.use_finbert:
                inputs = self.tokenizer(text_input, return_tensors="pt", padding=True, truncation=True, max_length=512)
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    
                probs = F.softmax(outputs.logits, dim=-1)
                probs_np = probs.numpy()[0]
                
                id2label = self.model.config.id2label
                pos_score = 0.0
                neg_score = 0.0
                
                for idx, label in id2label.items():
                    if "positive" in label.lower():
                        pos_score = probs_np[idx]
                    elif "negative" in label.lower():
                        neg_score = probs_np[idx]
                        
                sentiment_score = pos_score - neg_score
                return float(sentiment_score)
            
            return 0.0
            
        except Exception as e:
            print(f"Sentiment Error: {e}")
            return 0.0

# --- Signal 4: Simulated Attention Alpha (Google Trends Logic) ---
class AttentionSignalGenerator:
    def __init__(self):
        self.history = {} # symbol -> list of search volumes
        self.window = 24
        
    def update(self, symbol, current_volume):
        if symbol not in self.history:
            self.history[symbol] = []
        
        self.history[symbol].append(current_volume)
        if len(self.history[symbol]) > self.window:
            self.history[symbol].pop(0)
            
    def get_signal(self, symbol, current_volume):
        """
        Returns delta n (change in RSV).
        """
        if symbol not in self.history or len(self.history[symbol]) < 2:
            return 0.0
            
        baseline = sum(self.history[symbol]) / len(self.history[symbol])
        if baseline == 0: return 0.0
        
        delta_n = current_volume - baseline
        return float(delta_n)
