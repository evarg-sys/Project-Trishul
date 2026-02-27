import sys
sys.path.append('api/ml')
from disaster_detection import DisasterEnsembleSystem

system = DisasterEnsembleSystem(model_dir='api/ml/disaster_models')

training_texts = [
    'Apartment building on fire, residents trapped',
    'Restaurant fire spreading to neighboring buildings',
    'House fire on the west side, flames visible',
    'Smoke and flames coming from warehouse',
    'Major blaze at commercial building downtown',
    'Firefighters battling large building fire',
    'High rise building burning, evacuations underway',
    'Gas explosion caused fire in residential area',
    'Fire at school building, students evacuated',
    'Multiple cars on fire in parking garage',
    'River overflowed after heavy rain',
    'Flash flood warning issued',
    'Water entering homes',
    'Streets underwater after storm',
    'Heavy rain caused floods',
    'Strong earthquake felt across city',
    'Tremor shook buildings',
    'Earthquake damaged houses',
    'Magnitude 6 earthquake detected',
    'Buildings cracked after quake',
    'Sunny day at the beach',
    'Going to school today',
    'Nice weather outside',
    'Had lunch with friends',
    'Watching a movie tonight',
]

labels = ['fire','fire','fire','fire','fire','fire','fire','fire','fire','fire',
          'flood','flood','flood','flood','flood',
          'earthquake','earthquake','earthquake','earthquake','earthquake',
          'none','none','none','none','none']

severities = [5,4,5,4,4,4,5,4,5,5,
              4,3,4,3,4,
              5,3,4,5,4,
              1,1,1,1,1]

system.train_supervised(training_texts, labels, severities)
print('Model trained successfully!')