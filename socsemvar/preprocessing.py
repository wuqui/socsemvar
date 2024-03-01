# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/02_preprocessing.ipynb.

# %% auto 0
__all__ = ['log_step', 'conv_to_lowerc', 'rm_punct', 'tokenize', 'count_toks', 'rem_short_comments', 'clean_comments',
           'load_blacklist_lex']

# %% ../nbs/02_preprocessing.ipynb 3
from functools import wraps
import datetime as dt
import pandas as pd
import pandas.testing as pdt

# %% ../nbs/02_preprocessing.ipynb 5
def log_step(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        tic = dt.datetime.now()
        result = func(*args, **kwargs)
        time_taken = str(dt.datetime.now() - tic)
        print(f"{func.__name__:20} {str(result.shape):10} {time_taken:20}")
        return result
    return wrapper

# %% ../nbs/02_preprocessing.ipynb 7
@log_step
def conv_to_lowerc(comments: pd.DataFrame) -> pd.DataFrame:
	return comments\
            .assign(body=lambda x: x['body'].str.lower())

# %% ../nbs/02_preprocessing.ipynb 13
@log_step
def rm_punct(comments: pd.DataFrame) -> pd.DataFrame:
    return comments\
        .assign(body=lambda x: x['body'].str.replace(r'[^\w\s]+', ' ', regex=True))

# %% ../nbs/02_preprocessing.ipynb 18
@log_step
def tokenize(comments: pd.DataFrame) -> pd.DataFrame:
	return comments\
	.assign(body = lambda x: x['body'].str.split())

# %% ../nbs/02_preprocessing.ipynb 24
def count_toks(comments: pd.DataFrame) -> pd.DataFrame:
	return comments\
            .assign(toks=lambda x: x['body'].map(len))


# %% ../nbs/02_preprocessing.ipynb 29
@log_step
def rem_short_comments(comments: pd.DataFrame, min_toks: int=10) -> pd.DataFrame:
	return comments\
            .pipe(count_toks)\
            .query('toks > @min_toks')\
            .drop('toks', axis=1)
	

# %% ../nbs/02_preprocessing.ipynb 34
def clean_comments(comments: pd.DataFrame) -> pd.DataFrame:
	return comments\
            .pipe(conv_to_lowerc)\
            .pipe(rm_punct)\
            .pipe(tokenize)\
            .pipe(rem_short_comments)


# %% ../nbs/02_preprocessing.ipynb 39
def load_blacklist_lex(fpath: str='../../blacklist_lex.csv', propNouns: bool=True):
    blacklist_df = pd.read_csv('../../blacklist_lex.csv')
    if propNouns == True:
        return (blacklist_df
                .query('Excl == True')
                .loc[:, 'Lex']
        )
    elif propNouns == False:
        return (blacklist_df
                .query('Excl == True | Category == "propNoun"')
                .loc[:, 'Lex']
        )
