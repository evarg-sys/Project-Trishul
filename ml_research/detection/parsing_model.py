import numpy as np
import pickle
import os
from typing import Dict, List, Tuple, Optional
from collections import defaultdict, Counter
import json
from datetime import datetime

# Check available libraries
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.cluster import KMeans
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️ scikit-learn not available. Run: pip install scikit-learn")

try:
    from transformers import pipeline, AutoTokenizer, AutoModel
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("⚠️ transformers not available. Run: pip install transformers torch")

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    print("⚠️ sentence-transformers not available. Run: pip install sentence-transformers")

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    print("⚠️ spacy not available. Run: pip install spacy")


class DisasterEnsembleSystem:
    """
    Three-model ensemble system:
    1. Rule-based (fast, always available)
    2. Supervised learning (trained on labeled data)
    3. Unsupervised transformers (learns over time)
    """
    
    def __init__(self, model_dir='disaster_models'):
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)
        
        print("="*70)
        print("🚀 INITIALIZING ENSEMBLE DISASTER DETECTION SYSTEM")
        print("="*70)
        
        # Initialize all three models
        self._init_rule_based()
        self._init_supervised()
        self._init_unsupervised()
        
        # Learning history
        self.learning_history = []
        self.load_history()
        
        print(f"\n✅ System initialized with {len(self.learning_history)} historical examples")
        self._show_system_status()
    
    # ======================== MODEL 1: RULE-BASED ========================
    
    def _init_rule_based(self):
        """Initialize rule-based model"""
        print("\n📋 [Model 1] Initializing Rule-Based System...")
        
        self.rule_keywords = {
            'flood': {
                'primary': ['flood', 'flooding', 'flooded', 'flash flood', 'inundation'],
                'severity_high': ['major flood', 'catastrophic', 'dam breach'],
                'urgency': ['emergency', 'evacuate', 'help', 'urgent']
            },
            'fire': {
                'primary': ['fire', 'wildfire', 'blaze', 'burning', 'flames'],
                'severity_high': ['out of control', 'spreading rapidly', 'major fire'],
                'urgency': ['emergency', 'evacuate', 'help', 'urgent']
            },
            'earthquake': {
                'primary': ['earthquake', 'quake', 'tremor', 'seismic'],
                'severity_high': ['major earthquake', 'magnitude 7', 'magnitude 8'],
                'urgency': ['emergency', 'help', 'urgent', 'collapsed']
            }
        }
        
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load("en_core_web_sm")
                print("  ✓ spaCy loaded for NER")
            except:
                self.nlp = None
                print("  ⚠️ spaCy model not found")
        else:
            self.nlp = None
        
        print("  ✓ Rule-based model ready")
    
    def _detect_rule_based(self, text: str) -> Dict:
        """Rule-based detection"""
        text_lower = text.lower()
        results = {}
        
        for disaster_type, keywords in self.rule_keywords.items():
            score = 0
            matched = []
            
            # Check primary keywords
            for kw in keywords['primary']:
                if kw in text_lower:
                    score += 30
                    matched.append(kw)
            
            # Check severity
            for kw in keywords['severity_high']:
                if kw in text_lower:
                    score += 20
            
            # Check urgency
            for kw in keywords['urgency']:
                if kw in text_lower:
                    score += 10
            
            if score > 0:
                results[disaster_type] = {
                    'score': min(score, 100),
                    'matched_keywords': matched
                }
        
        if not results:
            return {'detected': False, 'confidence': 0}
        
        best = max(results.items(), key=lambda x: x[1]['score'])
        return {
            'detected': True,
            'disaster_type': best[0],
            'confidence': best[1]['score'],
            'confidence_level': 'high' if best[1]['score'] >= 70 else 'medium' if best[1]['score'] >= 40 else 'low',
            'matched_keywords': best[1]['matched_keywords']
        }
    
    # ======================== MODEL 2: SUPERVISED ========================
    
    def _init_supervised(self):
        """Initialize supervised learning model"""
        print("\n🎯 [Model 2] Initializing Supervised Learning System...")
        
        self.supervised_vectorizer = None
        self.supervised_classifier = None
        self.supervised_severity_model = None
        
        # Try to load existing model
        supervised_path = os.path.join(self.model_dir, 'supervised_model.pkl')
        if os.path.exists(supervised_path):
            try:
                with open(supervised_path, 'rb') as f:
                    data = pickle.load(f)
                self.supervised_vectorizer = data['vectorizer']
                self.supervised_classifier = data['classifier']
                self.supervised_severity_model = data.get('severity_model')
                print("  ✓ Loaded existing supervised model")
                return
            except:
                print("  ⚠️ Could not load supervised model")
        
        print("  ⚠️ No supervised model found (will train when data available)")
    
    def train_supervised(self, texts: List[str], labels: List[str], severities: List[int]):
        """Train supervised model on labeled data"""
        if not SKLEARN_AVAILABLE:
            print("❌ scikit-learn not available")
            return False
        
        print("\n🎯 Training Supervised Model...")
        print(f"  Training samples: {len(texts)}")
        
        # Vectorize
        self.supervised_vectorizer = TfidfVectorizer(max_features=500, ngram_range=(1, 2))
        X = self.supervised_vectorizer.fit_transform(texts)
        
        # Train classifier
        self.supervised_classifier = LogisticRegression(max_iter=1000, random_state=42)
        self.supervised_classifier.fit(X, labels)
        
        # Train severity model
        self.supervised_severity_model = LogisticRegression(max_iter=1000, random_state=42)
        self.supervised_severity_model.fit(X, severities)
        
        # Save
        supervised_path = os.path.join(self.model_dir, 'supervised_model.pkl')
        with open(supervised_path, 'wb') as f:
            pickle.dump({
                'vectorizer': self.supervised_vectorizer,
                'classifier': self.supervised_classifier,
                'severity_model': self.supervised_severity_model
            }, f)
        
        print("  ✅ Supervised model trained and saved")
        return True
    
    def _detect_supervised(self, text: str) -> Dict:
        """Supervised model detection"""
        if self.supervised_classifier is None:
            return {'detected': False, 'reason': 'model_not_trained'}
        
        X = self.supervised_vectorizer.transform([text])
        
        # Predict
        pred = self.supervised_classifier.predict(X)[0]
        proba = self.supervised_classifier.predict_proba(X)[0]
        confidence = max(proba) * 100
        
        # Severity
        severity = 3
        if self.supervised_severity_model:
            severity = self.supervised_severity_model.predict(X)[0]
        
        return {
            'detected': True,
            'disaster_type': pred,
            'confidence': confidence,
            'confidence_level': 'high' if confidence >= 70 else 'medium' if confidence >= 40 else 'low',
            'severity': int(severity),
            'all_probabilities': dict(zip(self.supervised_classifier.classes_, proba * 100))
        }
    
    # ======================== MODEL 3: UNSUPERVISED ========================
    
    def _init_unsupervised(self):
        """Initialize unsupervised transformer-based system"""
        print("\n🧠 [Model 3] Initializing Unsupervised Learning System...")
        
        self.sentence_encoder = None
        self.zero_shot_classifier = None
        self.cluster_model = None
        self.embeddings_cache = []
        self.cluster_labels = {}
        
        # Load sentence transformer for embeddings
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                print("  Loading sentence transformer...")
                self.sentence_encoder = SentenceTransformer('all-MiniLM-L6-v2')
                print("  ✓ Sentence encoder loaded")
            except:
                print("  ⚠️ Could not load sentence transformer")
        
        # Load zero-shot classifier
        if TRANSFORMERS_AVAILABLE:
            try:
                print("  Loading zero-shot classifier...")
                self.zero_shot_classifier = pipeline(
                    "zero-shot-classification",
                    model="facebook/bart-large-mnli",
                    device=-1  # CPU
                )
                print("  ✓ Zero-shot classifier loaded")
            except Exception as e:
                print(f"  ⚠️ Could not load zero-shot classifier: {e}")
        
        # Try to load existing clusters
        unsupervised_path = os.path.join(self.model_dir, 'unsupervised_model.pkl')
        if os.path.exists(unsupervised_path):
            try:
                with open(unsupervised_path, 'rb') as f:
                    data = pickle.load(f)
                self.cluster_model = data.get('cluster_model')
                self.cluster_labels = data.get('cluster_labels', {})
                print("  ✓ Loaded existing clusters")
            except:
                print("  ⚠️ Could not load unsupervised model")
        
        if not (self.sentence_encoder or self.zero_shot_classifier):
            print("  ⚠️ Unsupervised features limited (install transformers/sentence-transformers)")
    
    def _detect_unsupervised(self, text: str) -> Dict:
        """Unsupervised detection using transformers"""
        results = {'detected': False}
        
        # Method 1: Zero-shot classification
        if self.zero_shot_classifier:
            try:
                candidate_labels = ["flood disaster", "fire disaster", "earthquake disaster", "no disaster"]
                result = self.zero_shot_classifier(text, candidate_labels)
                
                top_label = result['labels'][0]
                top_score = result['scores'][0] * 100
                
                if 'disaster' in top_label and top_score > 30:
                    disaster_type = top_label.replace(' disaster', '')
                    results = {
                        'detected': True,
                        'disaster_type': disaster_type,
                        'confidence': top_score,
                        'confidence_level': 'high' if top_score >= 70 else 'medium' if top_score >= 40 else 'low',
                        'method': 'zero_shot',
                        'all_scores': dict(zip(result['labels'], [s*100 for s in result['scores']]))
                    }
            except Exception as e:
                print(f"Zero-shot error: {e}")
        
        # Method 2: Clustering-based detection
        if self.sentence_encoder and self.cluster_model:
            try:
                # Encode text
                embedding = self.sentence_encoder.encode([text])
                
                # Find cluster
                cluster_id = self.cluster_model.predict(embedding)[0]
                
                if cluster_id in self.cluster_labels:
                    cluster_info = self.cluster_labels[cluster_id]
                    results = {
                        'detected': True,
                        'disaster_type': cluster_info['type'],
                        'confidence': cluster_info.get('confidence', 50),
                        'confidence_level': 'medium',
                        'method': 'clustering',
                        'cluster_id': int(cluster_id)
                    }
            except Exception as e:
                print(f"Clustering error: {e}")
        
        return results
    
    def learn_from_examples(self, texts: List[str]):
        """Learn patterns from unlabeled examples"""
        if not self.sentence_encoder or not SKLEARN_AVAILABLE:
            print("❌ Unsupervised learning not available")
            return
        
        print(f"\n🧠 Learning from {len(texts)} examples...")
        
        # Encode all texts
        embeddings = self.sentence_encoder.encode(texts, show_progress_bar=True)
        self.embeddings_cache = embeddings
        
        # Cluster
        n_clusters = min(5, max(3, len(texts) // 10))
        self.cluster_model = KMeans(n_clusters=n_clusters, random_state=42)
        clusters = self.cluster_model.fit_predict(embeddings)
        
        # Analyze clusters
        self.cluster_labels = {}
        for cluster_id in range(n_clusters):
            cluster_texts = [texts[i] for i in range(len(texts)) if clusters[i] == cluster_id]
            
            # Find common words
            all_words = ' '.join(cluster_texts).lower().split()
            common_words = Counter(all_words).most_common(5)
            
            # Try to label cluster
            disaster_type = self._infer_cluster_type(common_words)
            
            self.cluster_labels[cluster_id] = {
                'type': disaster_type,
                'size': len(cluster_texts),
                'common_words': [w[0] for w in common_words],
                'examples': cluster_texts[:3],
                'confidence': 60
            }
        
        # Save
        unsupervised_path = os.path.join(self.model_dir, 'unsupervised_model.pkl')
        with open(unsupervised_path, 'wb') as f:
            pickle.dump({
                'cluster_model': self.cluster_model,
                'cluster_labels': self.cluster_labels
            }, f)
        
        print("✅ Learned new patterns!")
        self._show_clusters()
    
    def _infer_cluster_type(self, common_words):
        """Infer disaster type from common words"""
        word_list = [w[0] for w in common_words]
        
        flood_words = {'flood', 'water', 'river', 'rain'}
        fire_words = {'fire', 'burn', 'smoke', 'flame'}
        quake_words = {'earthquake', 'quake', 'tremor', 'seismic'}
        
        if any(w in flood_words for w in word_list):
            return 'flood'
        elif any(w in fire_words for w in word_list):
            return 'fire'
        elif any(w in quake_words for w in word_list):
            return 'earthquake'
        else:
            return 'unknown'
    
    def _show_clusters(self):
        """Display discovered clusters"""
        print("\n📊 Discovered Patterns:")
        for cluster_id, info in self.cluster_labels.items():
            print(f"\n  Cluster {cluster_id}: {info['type'].upper()}")
            print(f"    Size: {info['size']} examples")
            print(f"    Key words: {', '.join(info['common_words'])}")
    
    # ======================== ENSEMBLE LOGIC ========================
    
    def detect(self, text: str, return_all_models: bool = False) -> Dict:
        """
        Run all three models and combine results
        """
        print(f"\n🔍 Analyzing: \"{text[:60]}...\"")
        
        # Run all three models
        rule_result = self._detect_rule_based(text)
        supervised_result = self._detect_supervised(text)
        unsupervised_result = self._detect_unsupervised(text)
        
        print(f"\n  📋 Rule-based: {rule_result.get('disaster_type', 'N/A')} ({rule_result.get('confidence', 0):.1f}%)")
        print(f"  🎯 Supervised: {supervised_result.get('disaster_type', 'N/A')} ({supervised_result.get('confidence', 0):.1f}%)")
        print(f"  🧠 Unsupervised: {unsupervised_result.get('disaster_type', 'N/A')} ({unsupervised_result.get('confidence', 0):.1f}%)")
        
        # Combine results with weighted voting
        final_result = self._ensemble_vote(rule_result, supervised_result, unsupervised_result)
        
        # Add feedback mechanism
        final_result['individual_models'] = {
            'rule_based': rule_result,
            'supervised': supervised_result,
            'unsupervised': unsupervised_result
        }
        
        # Save to history
        self.learning_history.append({
            'text': text,
            'result': final_result,
            'timestamp': datetime.now().isoformat()
        })
        self.save_history()
        
        if return_all_models:
            return final_result
        
        # Return clean result
        return {
            'detected': final_result['detected'],
            'disaster_type': final_result.get('disaster_type'),
            'confidence': final_result.get('confidence', 0),
            'confidence_level': final_result.get('confidence_level'),
            'severity': final_result.get('severity', 3),
            'matched_keywords': final_result.get('matched_keywords', []),
            'ensemble_agreement': final_result.get('agreement')
        }
    
    def _ensemble_vote(self, rule_result, supervised_result, unsupervised_result):
        """Combine predictions from all three models"""
        votes = {}
        confidences = {}
        
        # Collect votes
        for result, weight in [(rule_result, 1.0), (supervised_result, 1.5), (unsupervised_result, 1.2)]:
            if result.get('detected'):
                disaster_type = result['disaster_type']
                confidence = result.get('confidence', 0)
                
                if disaster_type not in votes:
                    votes[disaster_type] = 0
                    confidences[disaster_type] = []
                
                votes[disaster_type] += weight
                confidences[disaster_type].append(confidence)
        
        if not votes:
            return {'detected': False, 'confidence': 0}
        
        # Find winner
        winner = max(votes.items(), key=lambda x: x[1])
        disaster_type = winner[0]
        avg_confidence = np.mean(confidences[disaster_type])
        
        # Agreement level
        num_models_agree = sum(1 for r in [rule_result, supervised_result, unsupervised_result] 
                              if r.get('detected') and r.get('disaster_type') == disaster_type)
        
        agreement = 'strong' if num_models_agree == 3 else 'moderate' if num_models_agree == 2 else 'weak'
        
        return {
            'detected': True,
            'disaster_type': disaster_type,
            'confidence': avg_confidence,
            'confidence_level': 'high' if avg_confidence >= 70 else 'medium' if avg_confidence >= 40 else 'low',
            'severity': supervised_result.get('severity', 3),
            'matched_keywords': rule_result.get('matched_keywords', []),
            'agreement': agreement,
            'voting_details': votes
        }
    
    def provide_feedback(self, text: str, correct_type: str, correct_severity: int):
        """User provides feedback to improve the system"""
        print(f"\n📝 Recording feedback: {text[:50]}... -> {correct_type} (severity: {correct_severity})")
        
        # Add to learning history with feedback
        self.learning_history.append({
            'text': text,
            'feedback': {
                'correct_type': correct_type,
                'correct_severity': correct_severity
            },
            'timestamp': datetime.now().isoformat()
        })
        
        # If we have enough feedback, retrain supervised model
        feedback_count = sum(1 for h in self.learning_history if 'feedback' in h)
        if feedback_count >= 10 and feedback_count % 10 == 0:
            print(f"\n🔄 Retraining with {feedback_count} feedback examples...")
            self._retrain_from_feedback()
    
    def _retrain_from_feedback(self):
        """Retrain supervised model using feedback"""
        feedback_examples = [h for h in self.learning_history if 'feedback' in h]
        
        texts = [h['text'] for h in feedback_examples]
        labels = [h['feedback']['correct_type'] for h in feedback_examples]
        severities = [h['feedback']['correct_severity'] for h in feedback_examples]
        
        self.train_supervised(texts, labels, severities)
    
    def _show_system_status(self):
        """Show status of all three models"""
        print("\n📊 System Status:")
        print(f"  📋 Rule-based: ✅ Active")
        print(f"  🎯 Supervised: {'✅ Trained' if self.supervised_classifier else '⚠️ Not trained'}")
        print(f"  🧠 Unsupervised: {'✅ Active' if self.zero_shot_classifier or self.sentence_encoder else '⚠️ Limited'}")
    
    def save_history(self):
        """Save learning history"""
        history_path = os.path.join(self.model_dir, 'learning_history.json')
        with open(history_path, 'w') as f:
            json.dump(self.learning_history, f, indent=2)
    
    def load_history(self):
        """Load learning history"""
        history_path = os.path.join(self.model_dir, 'learning_history.json')
        if os.path.exists(history_path):
            with open(history_path, 'r') as f:
                self.learning_history = json.load(f)


# Example usage
if __name__ == "__main__":

    system = DisasterEnsembleSystem()
    # ---------------- TRAINING DATA ----------------
    


    training_texts = [
        # FIRE
        "Huge fire downtown, buildings burning",
        "Wildfire spreading near forest",
        "House on fire, people trapped",
        "Smoke and flames seen across city",
        "Major blaze at warehouse",
        "Firefighters battling large fire",
        "Apartment building burning",
        "Gas explosion caused fire",
        "Forest fire out of control",
        "Fire near school, evacuations happening",

        # FLOOD
        "River overflowed after heavy rain",
        "Flash flood warning issued",
        "Water entering homes",
        "Streets underwater after storm",
        "Dam overflow causing flooding",
        "Heavy rain caused floods",
        "Flooded roads near downtown",
        "River rising rapidly",
        "Flood emergency declared",
        "People rescued from floodwaters",

        # EARTHQUAKE
        "Strong earthquake felt across city",
        "Tremor shook buildings",
        "Earthquake damaged houses",
        "Seismic activity reported",
        "Magnitude 6 earthquake detected",
        "Buildings cracked after quake",
        "Aftershock felt in region",
        "Major earthquake struck town",
        "Earthquake caused power outage",
        "Tremors continue overnight",

        # NO DISASTER (noise)
        "Sunny day at the beach",
        "Going to school today",
        "Nice weather outside",
        "Had lunch with friends",
        "Watching a movie tonight",
        "Studying for exams",
        "Shopping at mall",
        "Gym workout today",
        "Cooking dinner",
        "Reading a book"
    ]

    training_labels = [
        # FIRE (10)
        "fire","fire","fire","fire","fire","fire","fire","fire","fire","fire",

        # FLOOD (10)
        "flood","flood","flood","flood","flood","flood","flood","flood","flood","flood",

        # EARTHQUAKE (10)
        "earthquake","earthquake","earthquake","earthquake","earthquake",
        "earthquake","earthquake","earthquake","earthquake","earthquake",

        # NO DISASTER (10)
        "none","none","none","none","none","none","none","none","none","none"
    ]

    training_severities = [
        # FIRE
        5,4,5,4,4,4,5,4,5,5,
        # FLOOD
        4,3,4,3,5,4,3,4,5,4,
        # EARTHQUAKE
        5,3,4,3,5,4,3,5,4,3,
        # NONE
        1,1,1,1,1,1,1,1,1,1
    ]
    assert len(training_texts) == len(training_labels) == len(training_severities), "Dataset lengths do not match!"

    # Train supervised model
    system.train_supervised(training_texts, training_labels, training_severities)

    print("\n" + "="*70)
    print(" DISASTER DETECTION ENSEMBLE SYSTEM")
    print("="*70)
    
    # Initialize system
    
    
    # Test cases
    test_cases = [
        "URGENT: Major fire at downtown Chicago, multiple buildings burning!",
        "Flash flood warning, water levels rising rapidly, evacuate now!",
        "Earthquake magnitude 7.2 felt across the city, buildings damaged",
        "Nice sunny day today",
    ]
    
    print("\n" + "="*70)
    print(" TESTING ENSEMBLE SYSTEM")
    print("="*70)
    
    for text in test_cases:
        result = system.detect(text)
        print(f"\n{'='*70}")
        if result['detected']:
            print(f" {result['disaster_type'].upper()} detected")
            print(f"   Confidence: {result['confidence']:.1f}% ({result['confidence_level']})")
            print(f"   Agreement: {result.get('agreement', 'N/A')}")
        else:
            print(" No disaster detected")