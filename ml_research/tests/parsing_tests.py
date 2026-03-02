import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from parsing_model import DisasterNLPDetector
import json
from datetime import datetime

class DisasterNLPVisualizer:
    def __init__(self):
        print("=" * 70)
        print("INITIALIZING DISASTER NLP VISUALIZATION SYSTEM")
        print("=" * 70)
        print("Loading spaCy NLP model...")
        self.detector = DisasterNLPDetector()
        print("✓ System ready!\n")
    
    def analyze_and_visualize(self, text: str, output_file: str = "disaster_analysis.html"):
        """Analyze text and create HTML visualization"""
        
        # Run detection
        result = self.detector.detect_disaster(text)
        
        # Get detailed NLP analysis
        doc = self.detector.nlp(text.lower())
        
        # Collect NLP data
        nlp_data = self._collect_nlp_data(doc, result)
        
        # Generate HTML
        html_content = self._generate_html(text, result, nlp_data)
        
        # Save to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"\n✓ Visualization saved to: {output_file}")
        print(f"  Open it in your browser to view the analysis!")
        
        return output_file
    
    def _collect_nlp_data(self, doc, result):
        """Collect all NLP analysis data"""
        data = {}
        
        # 1. Tokenization
        data['tokens'] = [token.text for token in doc]
        
        # 2. Part-of-Speech tags
        pos_tags = {}
        for token in doc:
            pos = token.pos_
            if pos not in pos_tags:
                pos_tags[pos] = []
            pos_tags[pos].append({
                'text': token.text,
                'tag': token.tag_,
                'dep': token.dep_
            })
        data['pos_tags'] = pos_tags
        
        # 3. Named entities
        data['entities'] = []
        for ent in doc.ents:
            data['entities'].append({
                'text': ent.text,
                'label': ent.label_,
                'start': ent.start_char,
                'end': ent.end_char
            })
        
        # 4. Dependency structure
        data['dependencies'] = []
        for token in doc:
            if token.dep_ in ['ROOT', 'nsubj', 'dobj', 'pobj', 'amod', 'advmod']:
                data['dependencies'].append({
                    'text': token.text,
                    'dep': token.dep_,
                    'head': token.head.text
                })
        
        # 5. Keyword matching info
        if result['detected']:
            disaster_type = result['disaster_type']
            matches = result['all_detections'][disaster_type]['keyword_matches']
            data['keyword_matches'] = matches
        else:
            data['keyword_matches'] = None
        
        return data
    
    def _generate_html(self, text, result, nlp_data):
        """Generate HTML visualization"""
        
        # POS tag display names and colors
        pos_info = {
            'NOUN': {'name': 'Nouns', 'icon': '📦', 'color': '#3498db'},
            'VERB': {'name': 'Verbs', 'icon': '🏃', 'color': '#e74c3c'},
            'ADJ': {'name': 'Adjectives', 'icon': '🎨', 'color': '#9b59b6'},
            'ADV': {'name': 'Adverbs', 'icon': '⚡', 'color': '#f39c12'},
            'PROPN': {'name': 'Proper Nouns', 'icon': '📍', 'color': '#1abc9c'},
            'NUM': {'name': 'Numbers', 'icon': '🔢', 'color': '#34495e'},
            'ADP': {'name': 'Prepositions', 'icon': '🔗', 'color': '#95a5a6'},
            'DET': {'name': 'Determiners', 'icon': '👉', 'color': '#7f8c8d'},
            'PUNCT': {'name': 'Punctuation', 'icon': '✏️', 'color': '#bdc3c7'},
        }
        
        # Entity type info
        entity_info = {
            'GPE': {'name': 'Geo-Political Entity', 'icon': '🌍', 'color': '#27ae60'},
            'LOC': {'name': 'Location', 'icon': '📍', 'color': '#16a085'},
            'PERSON': {'name': 'Person', 'icon': '👤', 'color': '#2980b9'},
            'ORG': {'name': 'Organization', 'icon': '🏢', 'color': '#8e44ad'},
            'DATE': {'name': 'Date', 'icon': '📅', 'color': '#d35400'},
            'FAC': {'name': 'Facility', 'icon': '🏛️', 'color': '#c0392b'},
        }
        
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Disaster NLP Analysis</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        
        .timestamp {{
            opacity: 0.9;
            font-size: 0.9em;
        }}
        
        .content {{
            padding: 30px;
        }}
        
        .section {{
            margin-bottom: 40px;
            background: #f8f9fa;
            padding: 25px;
            border-radius: 15px;
            border-left: 5px solid #667eea;
        }}
        
        .section-title {{
            font-size: 1.8em;
            margin-bottom: 20px;
            color: #2c3e50;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .original-text {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            border: 2px solid #e0e0e0;
            font-size: 1.1em;
            line-height: 1.6;
            color: #34495e;
        }}
        
        .result-box {{
            background: white;
            padding: 25px;
            border-radius: 15px;
            margin-top: 15px;
        }}
        
        .result-detected {{
            border: 3px solid #27ae60;
            background: #e8f5e9;
        }}
        
        .result-not-detected {{
            border: 3px solid #e74c3c;
            background: #ffebee;
        }}
        
        .disaster-type {{
            font-size: 2em;
            font-weight: bold;
            color: #e74c3c;
            margin-bottom: 15px;
        }}
        
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }}
        
        .metric {{
            background: white;
            padding: 15px;
            border-radius: 10px;
            border: 2px solid #e0e0e0;
            text-align: center;
        }}
        
        .metric-label {{
            font-size: 0.9em;
            color: #7f8c8d;
            margin-bottom: 5px;
        }}
        
        .metric-value {{
            font-size: 1.8em;
            font-weight: bold;
            color: #2c3e50;
        }}
        
        .confidence-high {{ color: #27ae60; }}
        .confidence-medium {{ color: #f39c12; }}
        .confidence-low {{ color: #e74c3c; }}
        
        .severity-bar {{
            width: 100%;
            height: 30px;
            background: #ecf0f1;
            border-radius: 15px;
            overflow: hidden;
            margin-top: 10px;
        }}
        
        .severity-fill {{
            height: 100%;
            background: linear-gradient(90deg, #27ae60, #f39c12, #e74c3c);
            transition: width 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }}
        
        .token-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 15px;
        }}
        
        .token {{
            background: #3498db;
            color: white;
            padding: 8px 15px;
            border-radius: 20px;
            font-size: 0.95em;
        }}
        
        .pos-group {{
            margin-bottom: 20px;
            background: white;
            padding: 15px;
            border-radius: 10px;
            border-left: 4px solid #3498db;
        }}
        
        .pos-header {{
            font-weight: bold;
            font-size: 1.1em;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .pos-words {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        
        .pos-word {{
            background: #ecf0f1;
            padding: 6px 12px;
            border-radius: 15px;
            font-size: 0.9em;
        }}
        
        .entity {{
            display: inline-block;
            padding: 8px 15px;
            margin: 5px;
            border-radius: 20px;
            font-weight: 500;
            color: white;
        }}
        
        .keyword-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        
        .keyword-card {{
            background: white;
            padding: 15px;
            border-radius: 10px;
            border: 2px solid #e0e0e0;
        }}
        
        .keyword-card-title {{
            font-weight: bold;
            margin-bottom: 10px;
            color: #2c3e50;
        }}
        
        .keyword-count {{
            font-size: 2em;
            font-weight: bold;
            color: #3498db;
        }}
        
        .matched-keywords {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 15px;
        }}
        
        .keyword {{
            background: #e74c3c;
            color: white;
            padding: 6px 12px;
            border-radius: 15px;
            font-size: 0.9em;
        }}
        
        .score-breakdown {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-top: 15px;
        }}
        
        .score-item {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #ecf0f1;
        }}
        
        .score-item:last-child {{
            border-bottom: none;
            font-weight: bold;
            font-size: 1.2em;
            border-top: 2px solid #2c3e50;
            margin-top: 10px;
            padding-top: 15px;
        }}
        
        .dependency {{
            background: white;
            padding: 12px;
            margin: 8px 0;
            border-radius: 8px;
            border-left: 4px solid #9b59b6;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .dep-word {{
            font-weight: bold;
            color: #2c3e50;
        }}
        
        .dep-type {{
            background: #9b59b6;
            color: white;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.85em;
        }}
        
        .locations {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 15px;
        }}
        
        .location {{
            background: #27ae60;
            color: white;
            padding: 10px 20px;
            border-radius: 20px;
            font-size: 1.1em;
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔬 Disaster NLP Analysis Report</h1>
            <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="content">
"""
        
        # Original Text Section
        html += f"""
            <div class="section">
                <div class="section-title">📝 Original Input Text</div>
                <div class="original-text">{text}</div>
            </div>
"""
        
        # Detection Results Section
        html += """
            <div class="section">
                <div class="section-title">🎯 Detection Results</div>
"""
        
        if result['detected']:
            confidence_class = f"confidence-{result['confidence_level']}"
            severity_width = (result['severity_score'] / 5) * 100
            
            html += f"""
                <div class="result-box result-detected">
                    <div class="disaster-type">✅ {result['disaster_type'].upper()} DETECTED</div>
                    
                    <div class="metrics">
                        <div class="metric">
                            <div class="metric-label">Confidence Score</div>
                            <div class="metric-value {confidence_class}">{result['confidence_score']:.1f}%</div>
                            <div class="metric-label">{result['confidence_level'].upper()}</div>
                        </div>
                        
                        <div class="metric">
                            <div class="metric-label">Severity Level</div>
                            <div class="metric-value">{result['severity_score']}/5</div>
                            <div class="metric-label">{result['severity_description']}</div>
                        </div>
                    </div>
                    
                    <div class="severity-bar">
                        <div class="severity-fill" style="width: {severity_width}%">
                            {result['severity_score']}/5
                        </div>
                    </div>
"""
            
            if result['locations']:
                html += """
                    <div style="margin-top: 20px;">
                        <strong>📍 Locations Detected:</strong>
                        <div class="locations">
"""
                for loc in result['locations']:
                    html += f'<div class="location">{loc}</div>'
                html += """
                        </div>
                    </div>
"""
            
            html += "</div>"
        else:
            html += f"""
                <div class="result-box result-not-detected">
                    <div class="disaster-type">❌ NO DISASTER DETECTED</div>
                    <p style="margin-top: 10px; color: #7f8c8d;">{result.get('message', 'The text does not contain clear disaster indicators.')}</p>
                </div>
"""
        
        html += "</div>"
        
        # Tokenization Section
        html += f"""
            <div class="section">
                <div class="section-title">1️⃣ Tokenization</div>
                <p style="margin-bottom: 15px; color: #7f8c8d;">Breaking text into {len(nlp_data['tokens'])} individual tokens/words</p>
                <div class="token-list">
"""
        for token in nlp_data['tokens']:
            html += f'<div class="token">{token}</div>'
        html += """
                </div>
            </div>
"""
        
        # Part-of-Speech Tagging Section
        html += """
            <div class="section">
                <div class="section-title">2️⃣ Part-of-Speech Tagging</div>
                <p style="margin-bottom: 15px; color: #7f8c8d;">Identifying the grammatical role of each word</p>
"""
        
        for pos, words in sorted(nlp_data['pos_tags'].items()):
            info = pos_info.get(pos, {'name': pos, 'icon': '•', 'color': '#95a5a6'})
            html += f"""
                <div class="pos-group" style="border-left-color: {info['color']}">
                    <div class="pos-header" style="color: {info['color']}">
                        <span>{info['icon']}</span>
                        <span>{info['name']}</span>
                        <span style="color: #95a5a6;">({len(words)})</span>
                    </div>
                    <div class="pos-words">
"""
            for word in words:
                html += f'<div class="pos-word">{word["text"]}</div>'
            html += """
                    </div>
                </div>
"""
        
        html += "</div>"
        
        # Named Entity Recognition Section
        html += """
            <div class="section">
                <div class="section-title">3️⃣ Named Entity Recognition</div>
                <p style="margin-bottom: 15px; color: #7f8c8d;">Extracting important entities from the text</p>
"""
        
        if nlp_data['entities']:
            for ent in nlp_data['entities']:
                info = entity_info.get(ent['label'], {'name': ent['label'], 'icon': '•', 'color': '#95a5a6'})
                html += f"""
                <div class="entity" style="background-color: {info['color']}">
                    {info['icon']} {ent['text']} <span style="opacity: 0.8; font-size: 0.85em;">({info['name']})</span>
                </div>
"""
        else:
            html += '<p style="color: #95a5a6; font-style: italic;">No named entities detected</p>'
        
        html += "</div>"
        
        # Dependency Parsing Section
        html += """
            <div class="section">
                <div class="section-title">4️⃣ Dependency Parsing</div>
                <p style="margin-bottom: 15px; color: #7f8c8d;">Understanding sentence structure and relationships</p>
"""
        
        dep_names = {
            'ROOT': 'Main Verb (Root)',
            'nsubj': 'Subject',
            'dobj': 'Direct Object',
            'pobj': 'Object of Preposition',
            'amod': 'Adjectival Modifier',
            'advmod': 'Adverbial Modifier'
        }
        
        for dep in nlp_data['dependencies']:
            dep_label = dep_names.get(dep['dep'], dep['dep'])
            html += f"""
                <div class="dependency">
                    <span class="dep-word">"{dep['text']}"</span>
                    <div>
                        <span class="dep-type">{dep_label}</span>
                        <span style="color: #95a5a6; margin-left: 10px;">→ {dep['head']}</span>
                    </div>
                </div>
"""
        
        html += "</div>"
        
        # Keyword Matching Section (only if disaster detected)
        if result['detected'] and nlp_data['keyword_matches']:
            matches = nlp_data['keyword_matches']
            
            html += """
            <div class="section">
                <div class="section-title">🔍 Keyword Matching Analysis</div>
                
                <div class="keyword-grid">
"""
            
            keyword_categories = [
                ('Primary Keywords', matches['primary_count'], '#e74c3c'),
                ('Secondary Keywords', matches['secondary_count'], '#f39c12'),
                ('High Severity Terms', matches['high_severity_count'], '#c0392b'),
                ('Urgency Words', matches['urgency_count'], '#e67e22'),
                ('Damage Indicators', matches['damage_count'], '#d35400'),
                ('Severity Modifiers', matches['severity_modifier_count'], '#8e44ad')
            ]
            
            for label, count, color in keyword_categories:
                html += f"""
                    <div class="keyword-card">
                        <div class="keyword-card-title">{label}</div>
                        <div class="keyword-count" style="color: {color}">{count}</div>
                    </div>
"""
            
            html += "</div>"
            
            # Matched keywords
            if matches['matched_keywords']:
                html += """
                    <div style="margin-top: 20px;">
                        <strong>Matched Keywords:</strong>
                        <div class="matched-keywords">
"""
                for kw in matches['matched_keywords']:
                    html += f'<div class="keyword">{kw}</div>'
                html += """
                        </div>
                    </div>
"""
            
            # Score breakdown
            html += """
                <div class="score-breakdown">
                    <h3 style="margin-bottom: 15px;">📊 Confidence Score Breakdown</h3>
"""
            
            score_items = []
            if matches['primary_count'] > 0:
                points = min(matches['primary_count'] * 15, 30)
                score_items.append(('Primary keywords', f"+{points}"))
            
            if matches['secondary_count'] > 0:
                points = min(matches['secondary_count'] * 10, 20)
                score_items.append(('Secondary keywords', f"+{points}"))
            
            if matches['high_severity_count'] > 0:
                score_items.append(('High severity terms', "+20"))
            
            if matches['urgency_count'] > 0:
                points = min(matches['urgency_count'] * 5, 15)
                score_items.append(('Urgency words', f"+{points}"))
            
            if matches['damage_count'] > 0:
                points = min(matches['damage_count'] * 5, 15)
                score_items.append(('Damage indicators', f"+{points}"))
            
            for label, points in score_items:
                html += f"""
                    <div class="score-item">
                        <span>{label}</span>
                        <span style="color: #27ae60; font-weight: bold;">{points}</span>
                    </div>
"""
            
            html += f"""
                    <div class="score-item">
                        <span>TOTAL CONFIDENCE</span>
                        <span style="color: #2c3e50;">{result['confidence_score']:.1f}%</span>
                    </div>
                </div>
"""
            
            html += "</div>"
        
        html += """
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def run_interactive(self):
        """Run interactive mode"""
        while True:
            print("\n" + "=" * 70)
            print("🎨 DISASTER NLP HTML VISUALIZER")
            print("=" * 70)
            print("1) Analyze text and generate HTML visualization")
            print("2) Exit")
            print("=" * 70)
            
            choice = input("\nChoose an option: ").strip()
            
            if choice == "2":
                print("\n👋 Exiting. Stay safe!")
                break
            
            if choice != "1":
                print("❌ Invalid choice. Please try again.")
                continue
            
            # Get input
            print("\n" + "-" * 70)
            print("Enter disaster text to analyze:")
            print("-" * 70)
            text = input(">>> ").strip()
            
            if not text:
                print("❌ Empty input. Please enter some text.")
                continue
            
            # Get filename
            default_name = f"disaster_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            filename = input(f"\nSave as (press Enter for '{default_name}'): ").strip()
            if not filename:
                filename = default_name
            
            if not filename.endswith('.html'):
                filename += '.html'
            
            # Generate visualization
            print(f"\n🔄 Processing text and generating visualization...")
            self.analyze_and_visualize(text, filename)
            
            # Continue?
            cont = input("\nAnalyze another text? (y/n): ").strip().lower()
            if cont != 'y':
                print("\n👋 Exiting. Stay safe!")
                break


if __name__ == "__main__":
    visualizer = DisasterNLPVisualizer()
    visualizer.run_interactive()