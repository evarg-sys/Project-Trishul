# Project-Trishul

This repository contains the backend and frontend code for an emergency
response prototype called *Trishul*.  The system ingests user‑reported
incidents, runs a series of machine‑learning models to estimate severity
and affected population, and then prioritizes events before dispatching
resources.

## Priority model

A simple formula is used to score incidents:

```
priority = severity_score * population_affected
# optionally divide by an estimated response_time to boost nearby events
```

The logic lives in ``backend/api/ml/priority_model.py`` and is invoked
from the analysis task.  The score is stored on the ``Disaster`` model
and is used to order active reports in the API.

