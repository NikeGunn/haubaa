# Skill: machine-learning

## Capabilities
- Data preprocessing and feature engineering
- Model training with scikit-learn (classification, regression, clustering)
- Model evaluation (accuracy, precision, recall, F1, ROC-AUC)
- Hyperparameter tuning (grid search, random search)
- Model serialization and loading (joblib, pickle)
- Visualization of results (confusion matrix, feature importance, learning curves)
- Train/test split and cross-validation

## When To Use
- Training machine learning models on structured data
- Evaluating and comparing model performance
- Building prediction or classification pipelines
- Task mentions "ML", "machine learning", "train model", "predict", "classify", "regression", "scikit-learn"

## Tools Required
- scikit-learn
- pandas
- matplotlib
- joblib

## Approach

### Phase 1: Understand
- Identify the problem type (classification, regression, clustering)
- Examine the dataset: features, target, size, balance
- Check for data quality issues (missing values, outliers, class imbalance)
- Define success metrics appropriate for the problem

### Phase 2: Plan
- Design feature engineering pipeline (encoding, scaling, selection)
- Select candidate algorithms based on problem type and data characteristics
- Plan train/test/validation split strategy
- Define hyperparameter search space

### Phase 3: Execute
- Install scikit-learn and dependencies if needed
- Load and preprocess data (handle missing values, encode categoricals)
- Engineer features (scaling, polynomial, interactions)
- Split data with stratification if classification
- Train multiple candidate models with default parameters
- Evaluate and compare models on validation set
- Tune best model with hyperparameter search
- Generate evaluation plots (confusion matrix, ROC curve, feature importance)
- Serialize final model with joblib

### Phase 4: Verify
- Verify test set performance matches validation (no data leakage)
- Check for overfitting (train vs test performance gap)
- Validate predictions on a few known examples
- Confirm serialized model loads and predicts correctly
- Document model performance and limitations

## Constraints
- Always split data before any preprocessing that uses statistics (prevent leakage)
- Use pipelines (sklearn.pipeline) to encapsulate preprocessing + model
- Never evaluate on training data — always use held-out test set
- Report multiple metrics, not just accuracy (especially for imbalanced data)
- Document feature engineering decisions and model assumptions

## Scale Considerations
- For large datasets, use incremental learning or sampling for exploration
- Use sparse matrices for high-dimensional data
- Parallelize hyperparameter search with n_jobs=-1
- Consider gradient boosting (XGBoost, LightGBM) for tabular data > 10K rows

## Error Recovery
- Convergence warning: increase max_iter, scale features, try different solver
- Memory error: reduce dataset size, use sparse representations
- Poor performance: add features, try different algorithms, collect more data
- Data leakage detected: rebuild pipeline with proper train/test separation
