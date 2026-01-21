import spacy
from typing import Dict, List, Tuple
import re

class DisasterNLPDetector:
    def __init__(self):
        """Initialize the disaster detector with spaCy"""
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("Downloading spaCy model...")
            import os
            os.system("python -m spacy download en_core_web_sm")
            self.nlp = spacy.load("en_core_web_sm")
        
        # Define disaster types and their keywords
        self.disaster_keywords = {
            'flood': {
                'primary': ['flood', 'flooding', 'flooded', 'flash flood', 'river overflow', 
                           'water rising', 'inundation', 'deluge'],
                'secondary': ['water', 'submerged', 'waterlogged', 'downstream', 'dam breach'],
                'high_severity': ['major flood', 'severe flooding', 'catastrophic flood', 
                                'flash flood', 'dam failure', 'levee breach'],
                'severity_modifiers': ['massive', 'severe', 'major', 'catastrophic', 
                                      'devastating', 'unprecedented', 'historic']
            },
            'fire': {
                'primary': ['fire', 'wildfire', 'forest fire', 'blaze', 'inferno', 
                           'bushfire', 'structure fire'],
                'secondary': ['burning', 'flames', 'smoke', 'combustion', 'conflagration', 
                             'ablaze', 'ignited'],
                'high_severity': ['major fire', 'out of control', 'spreading rapidly', 
                                'wildfire', 'firestorm', 'multiple alarm'],
                'severity_modifiers': ['massive', 'uncontrolled', 'spreading', 'engulfing', 
                                      'raging', 'intense', 'growing']
            },
            'earthquake': {
                'primary': ['earthquake', 'quake', 'tremor', 'seismic', 'temblor', 
                           'earth shake'],
                'secondary': ['shaking', 'magnitude', 'epicenter', 'aftershock', 'richter', 
                             'ground shaking', 'seismic activity'],
                'high_severity': ['major earthquake', 'strong earthquake', 'devastating quake', 
                                'magnitude 6', 'magnitude 7', 'magnitude 8'],
                'severity_modifiers': ['massive', 'strong', 'powerful', 'devastating', 
                                      'major', 'violent', 'severe']
            }
        }
        
        # Urgency keywords that increase confidence
        self.urgency_keywords = [
            'emergency', 'urgent', 'immediate', 'critical', 'help', 'sos',
            'evacuation', 'evacuate', 'danger', 'warning', 'alert', 'rescue',
            'mayday', 'crisis', 'please help', 'need help'
        ]
        
        # Casualty/damage keywords that increase severity
        self.damage_keywords = [
            'casualties', 'injuries', 'deaths', 'trapped', 'collapsed',
            'destroyed', 'damage', 'victims', 'missing', 'dead', 'injured',
            'fatalities', 'hurt', 'wounded', 'buried', 'stranded'
        ]
        
        # Location indicators for extraction
        self.location_indicators = [
            'at', 'in', 'near', 'on', 'around', 'location', 'address',
            'street', 'avenue', 'road', 'boulevard', 'drive', 'place'
        ]

    def preprocess_text(self, text: str) -> str:
        """Pre-processing: normalize text"""
        if not text:
            return ""
        # Convert to lowercase
        text = text.lower()
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text

    def extract_location(self, doc) -> List[str]:
        """Extract location entities using spaCy NER"""
        locations = []
        
        # Extract GPE (Geo-Political Entity) and LOC (Location) entities
        for ent in doc.ents:
            if ent.label_ in ['GPE', 'LOC', 'FAC']:
                locations.append(ent.text)
        
        # Look for addresses using pattern matching
        text = doc.text.lower()
        
        # Pattern for street addresses
        address_pattern = r'\d+\s+[A-Za-z\s]+(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|way|court|ct)'
        addresses = re.findall(address_pattern, text, re.IGNORECASE)
        locations.extend(addresses)
        
        return list(set(locations))  # Remove duplicates

    def calculate_confidence_score(self, text: str, disaster_type: str, 
                                   keyword_matches: Dict) -> Tuple[float, str]:
        """
        Calculate confidence score based on keyword matches and context
        Returns: (confidence_score, confidence_level)
        """
        score = 0.0
        
        # Base score from primary keywords (30 points)
        if keyword_matches['primary_count'] > 0:
            score += min(keyword_matches['primary_count'] * 15, 30)
        
        # Secondary keywords (20 points)
        if keyword_matches['secondary_count'] > 0:
            score += min(keyword_matches['secondary_count'] * 10, 20)
        
        # High severity keywords (20 points)
        if keyword_matches['high_severity_count'] > 0:
            score += 20
        
        # Urgency keywords (15 points)
        if keyword_matches['urgency_count'] > 0:
            score += min(keyword_matches['urgency_count'] * 5, 15)
        
        # Damage keywords (15 points)
        if keyword_matches['damage_count'] > 0:
            score += min(keyword_matches['damage_count'] * 5, 15)
        
        # Normalize to 0-100
        score = min(score, 100)
        
        # Determine confidence level
        if score >= 70:
            confidence_level = "high"
        elif score >= 40:
            confidence_level = "medium"
        else:
            confidence_level = "low"
        
        return score, confidence_level

    def calculate_severity(self, text: str, disaster_type: str, 
                          keyword_matches: Dict) -> Tuple[int, str]:
        """
        Calculate severity level (1-5 scale)
        Returns: (severity_score, severity_description)
        """
        severity = 1
        
        # Check for high severity keywords
        if keyword_matches['high_severity_count'] > 0:
            severity = max(severity, 4)
        
        # Check for severity modifiers
        if keyword_matches['severity_modifier_count'] > 0:
            severity += 1
        
        # Check for damage/casualty keywords
        if keyword_matches['damage_count'] > 0:
            severity += 1
        
        # Check for urgency
        if keyword_matches['urgency_count'] >= 2:
            severity += 1
        
        # Cap at 5
        severity = min(severity, 5)
        
        # Severity descriptions
        severity_descriptions = {
            1: "Minor",
            2: "Moderate",
            3: "Serious",
            4: "Severe",
            5: "Critical/Catastrophic"
        }
        
        return severity, severity_descriptions[severity]

    def detect_disaster(self, text: str) -> Dict:
        """
        Main detection function - analyzes text and returns disaster info
        """
        if not text or not text.strip():
            return {
                'detected': False,
                'error': 'Empty text provided'
            }
        
        # Preprocess and parse with spaCy
        processed_text = self.preprocess_text(text)
        doc = self.nlp(processed_text)
        
        # Extract locations
        locations = self.extract_location(doc)
        
        # Check each disaster type
        disaster_scores = {}
        
        for disaster_type, keywords in self.disaster_keywords.items():
            # Count keyword matches
            keyword_matches = {
                'primary_count': 0,
                'secondary_count': 0,
                'high_severity_count': 0,
                'severity_modifier_count': 0,
                'urgency_count': 0,
                'damage_count': 0,
                'matched_keywords': []
            }
            
            # Check primary keywords
            for keyword in keywords['primary']:
                if keyword in processed_text:
                    keyword_matches['primary_count'] += 1
                    keyword_matches['matched_keywords'].append(keyword)
            
            # Check secondary keywords
            for keyword in keywords['secondary']:
                if keyword in processed_text:
                    keyword_matches['secondary_count'] += 1
                    keyword_matches['matched_keywords'].append(keyword)
            
            # Check high severity keywords
            for keyword in keywords['high_severity']:
                if keyword in processed_text:
                    keyword_matches['high_severity_count'] += 1
                    keyword_matches['matched_keywords'].append(keyword)
            
            # Check severity modifiers
            for modifier in keywords['severity_modifiers']:
                if modifier in processed_text:
                    keyword_matches['severity_modifier_count'] += 1
            
            # Check urgency keywords
            for keyword in self.urgency_keywords:
                if keyword in processed_text:
                    keyword_matches['urgency_count'] += 1
            
            # Check damage keywords
            for keyword in self.damage_keywords:
                if keyword in processed_text:
                    keyword_matches['damage_count'] += 1
            
            # Calculate confidence and severity
            confidence_score, confidence_level = self.calculate_confidence_score(
                processed_text, disaster_type, keyword_matches
            )
            
            severity_score, severity_description = self.calculate_severity(
                processed_text, disaster_type, keyword_matches
            )
            
            # Store results if any keywords matched
            if keyword_matches['primary_count'] > 0 or keyword_matches['secondary_count'] > 0:
                disaster_scores[disaster_type] = {
                    'confidence_score': confidence_score,
                    'confidence_level': confidence_level,
                    'severity_score': severity_score,
                    'severity_description': severity_description,
                    'keyword_matches': keyword_matches,
                    'locations': locations
                }
        
        # Determine the most likely disaster type
        if disaster_scores:
            best_match = max(disaster_scores.items(), 
                           key=lambda x: x[1]['confidence_score'])
            
            return {
                'detected': True,
                'disaster_type': best_match[0],
                'confidence_score': best_match[1]['confidence_score'],
                'confidence_level': best_match[1]['confidence_level'],
                'severity_score': best_match[1]['severity_score'],
                'severity_description': best_match[1]['severity_description'],
                'locations': best_match[1]['locations'],
                'matched_keywords': best_match[1]['keyword_matches']['matched_keywords'][:5],
                'all_detections': disaster_scores,
                'original_text': text
            }
        else:
            return {
                'detected': False,
                'message': 'No disaster detected in text',
                'original_text': text
            }

    def print_results(self, result: Dict):
        """Pretty print the detection results"""
        print("\n" + "="*60)
        print("DISASTER DETECTION RESULTS")
        print("="*60)
        
        if not result['detected']:
            print(f"❌ {result.get('message', result.get('error', 'Unknown error'))}")
            return
        
        print(f"✅ DISASTER DETECTED: {result['disaster_type'].upper()}")
        print("-"*60)
        print(f"📊 Confidence: {result['confidence_score']:.1f}% ({result['confidence_level']})")
        print(f"⚠️  Severity: {result['severity_score']}/5 - {result['severity_description']}")
        
        if result['locations']:
            print(f"📍 Locations: {', '.join(result['locations'])}")
        
        print(f"🔑 Matched Keywords: {', '.join(result['matched_keywords'])}")
        
        if len(result['all_detections']) > 1:
            print("\n📋 Other Possible Disasters:")
            for disaster_type, info in result['all_detections'].items():
                if disaster_type != result['disaster_type']:
                    print(f"   - {disaster_type}: {info['confidence_score']:.1f}% confidence")
        
        print("="*60 + "\n")