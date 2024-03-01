# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/03_embeddings.ipynb.

# %% auto 0
__all__ = ['Corpus', 'train_model', 'load_models', 'intersection_align_gensim', 'smart_procrustes_align_gensim',
           'measure_distances', 'get_change_candidates', 'get_nearest_neighbours_models', 'get_pole_avg',
           'make_sem_axis_avg', 'get_axis_sim', 'get_axis_sims', 'aggregate_proj_sims', 'plot_sem_axis', 'get_nbs_vecs',
           'dim_red_nbs_vecs']

# %% ../nbs/03_embeddings.ipynb 3
from .read_data import *
from .preprocessing import *

# %% ../nbs/03_embeddings.ipynb 4
from gensim.models import Word2Vec
import numpy as np
import pandas as pd
from scipy import spatial
import altair as alt
from sklearn.manifold import TSNE

# %% ../nbs/03_embeddings.ipynb 8
class Corpus:
    """An iterator that yields sentences (lists of str)."""
    def __init__(self, docs):
        self.docs_clean = docs

    def __iter__(self):
        for doc in self.docs_clean:
            yield doc

# %% ../nbs/03_embeddings.ipynb 11
def train_model(corpus,
              MIN_COUNT=5,
              SIZE=300,
              WORKERS=8,
              WINDOW=5,
              EPOCHS=5
              ):
    model = Word2Vec(
        corpus,
        min_count=MIN_COUNT,
        vector_size=SIZE,
        workers=WORKERS,
        window=WINDOW,
        epochs=EPOCHS
    )
    return model


# %% ../nbs/03_embeddings.ipynb 14
def load_models(model_names: list, models_dir: str='../models_test') -> dict:
    models = {}
    for name in model_names:
        try:
            models[name] = Word2Vec.load(f'{models_dir}/{name}.model')
        except FileNotFoundError:
            print(f"Model '{name}' not found in '{models_dir}'.")
    return models

# %% ../nbs/03_embeddings.ipynb 18
def intersection_align_gensim(m1, m2, words=None):
    """
    Intersect two gensim word2vec models, m1 and m2.
    Only the shared vocabulary between them is kept.
    If 'words' is set (as list or set), then the vocabulary is intersected with this list as well.
    Indices are re-organized from 0..N in order of descending frequency (=sum of counts from both m1 and m2).
    These indices correspond to the new syn0 and syn0norm objects in both gensim models:
        -- so that Row 0 of m1.syn0 will be for the same word as Row 0 of m2.syn0
        -- you can find the index of any word on the .index2word list: model.index2word.index(word) => 2
    The .vocab dictionary is also updated for each model, preserving the count but updating the index.
    """

    # Get the vocab for each model
    vocab_m1 = set(m1.wv.index_to_key)
    vocab_m2 = set(m2.wv.index_to_key)

    # Find the common vocabulary
    common_vocab = vocab_m1 & vocab_m2
    if words: common_vocab &= set(words)

    # If no alignment necessary because vocab is identical...
    if not vocab_m1 - common_vocab and not vocab_m2 - common_vocab:
        return (m1,m2)

    # Otherwise sort by frequency (summed for both)
    common_vocab = list(common_vocab)
    common_vocab.sort(key=lambda w: m1.wv.get_vecattr(w, "count") + m2.wv.get_vecattr(w, "count"), reverse=True)
    # print(len(common_vocab))

    # Then for each model...
    for m in [m1, m2]:
        # Replace old syn0norm array with new one (with common vocab)
        indices = [m.wv.key_to_index[w] for w in common_vocab]
        old_arr = m.wv.vectors
        new_arr = np.array([old_arr[index] for index in indices])
        m.wv.vectors = new_arr

        # Replace old vocab dictionary with new one (with common vocab)
        # and old index2word with new one
        new_key_to_index = {}
        new_index_to_key = []
        for new_index, key in enumerate(common_vocab):
            new_key_to_index[key] = new_index
            new_index_to_key.append(key)
        m.wv.key_to_index = new_key_to_index
        m.wv.index_to_key = new_index_to_key
        
        print(len(m.wv.key_to_index), len(m.wv.vectors))
        
    return (m1,m2)

# %% ../nbs/03_embeddings.ipynb 19
def smart_procrustes_align_gensim(base_embed, other_embed, words=None):
    """
    Original script: https://gist.github.com/quadrismegistus/09a93e219a6ffc4f216fb85235535faf
    Procrustes align two gensim word2vec models (to allow for comparison between same word across models).
    Code ported from HistWords <https://github.com/williamleif/histwords> by William Hamilton <wleif@stanford.edu>.
        
    First, intersect the vocabularies (see `intersection_align_gensim` documentation).
    Then do the alignment on the other_embed model.
    Replace the other_embed model's syn0 and syn0norm numpy matrices with the aligned version.
    Return other_embed.
    If `words` is set, intersect the two models' vocabulary with the vocabulary in words (see `intersection_align_gensim` documentation).
    """

    # make sure vocabulary and indices are aligned
    in_base_embed, in_other_embed = intersection_align_gensim(base_embed, other_embed, words=words)

    # get the (normalized) embedding matrices
    base_vecs = in_base_embed.wv.get_normed_vectors()
    other_vecs = in_other_embed.wv.get_normed_vectors()

    # just a matrix dot product with numpy
    m = other_vecs.T.dot(base_vecs) 
    # SVD method from numpy
    u, _, v = np.linalg.svd(m)
    # another matrix operation
    ortho = u.dot(v) 
    # Replace original array with modified one, i.e. multiplying the embedding matrix by "ortho"
    other_embed.wv.vectors = (other_embed.wv.vectors).dot(ortho)    
    
    return other_embed

# %% ../nbs/03_embeddings.ipynb 23
def measure_distances(model_1, model_2):
    distances = pd.DataFrame(
        columns=('lex', 'dist_sem', "freq_1", "freq_2"),
        data=(
            #[w, spatial.distance.euclidean(model_1.wv[w], model_2.wv[w]),
            #[w, np.sum(model_1.wv[w] * model_2.wv[w]) / (np.linalg.norm(model_1.wv[w]) * np.linalg.norm(model_2.wv[w])),
            [w, spatial.distance.cosine(model_1.wv[w], model_2.wv[w]),
             model_1.wv.get_vecattr(w, "count"),
             model_2.wv.get_vecattr(w, "count")
             ] for w in model_1.wv.index_to_key
        )
    )
    return distances

# %% ../nbs/03_embeddings.ipynb 25
def get_change_candidates(k: int, distances: pd.DataFrame, freq_min: int = 100, propNouns: bool = True):
    blacklist_lex = load_blacklist_lex(propNouns=propNouns)
    return (distances\
        .query('freq_1 > @freq_min and freq_2 > @freq_min')
        .query('lex.str.isalpha() == True')
        .query('lex.str.len() > 3')
        .query('lex not in @blacklist_lex')
        .filter(['lex', 'dist_sem'])
        .nlargest(k, 'dist_sem')
        .assign(dist_sem=lambda df: round(df['dist_sem'], 2))
        .reset_index(drop=True)
    )

# %% ../nbs/03_embeddings.ipynb 27
def get_nearest_neighbours_models(lex: str, freq_min: int, model_1, model_2, topn: int=100_000, k: int=10):
    nbs = []
    for count, model in enumerate([model_1, model_2]):
        for nb, sim in model.wv.most_similar(lex, topn=topn):
            if model.wv.get_vecattr(nb, 'count') > freq_min:
                d = {}
                d['Model'] = count + 1
                d['Word'] = nb
                d['SemDist'] = round(1 - sim, 2)
                d['Freq'] = model.wv.get_vecattr(nb, "count")
                d['vec'] = model.wv.get_vector(lex)
                nbs.append(d)
    nbs_df = pd.DataFrame(nbs)
    nbs_df = nbs_df\
        .query('Freq > @freq_min')\
        .groupby('Model', group_keys=False)\
        .apply(lambda group: group.nsmallest(k, 'SemDist'))
    nbs_model_1 = nbs_df.query('Model == 1')
    nbs_model_2 = nbs_df.query('Model == 2')
    return nbs_model_1, nbs_model_2

# %% ../nbs/03_embeddings.ipynb 33
def get_pole_avg(model_name: str, model: Word2Vec, lex, k=10):
	words = []
	vecs = []
	vecs.append(model.wv[lex])
	df = (pd.read_csv(f"../pole-words/{model_name}_{lex}.csv")
		.query('Include != "f"')
		.nlargest(k, 'SemSim')
	)
	pole_words = df['Word'].tolist()
	for word in pole_words:
		if word in model.wv:
			vecs.append(model.wv[word])
			words.append(word)
	pole_avg = np.mean(vecs, axis=0)
	return pole_avg

# %% ../nbs/03_embeddings.ipynb 35
def make_sem_axis_avg(model_name: str, model: Word2Vec, pole_word_1: str, pole_word_2: str, k=10):
	pole_1_avg = get_pole_avg(model_name, model, pole_word_1, k)
	pole_2_avg = get_pole_avg(model_name, model, pole_word_2, k)
	sem_axis = pole_1_avg - pole_2_avg
	return sem_axis

# %% ../nbs/03_embeddings.ipynb 37
def get_axis_sim(lex: str, pole_word_1: str, pole_word_2: str, model_name, model, k=10):
	sem_axis = make_sem_axis_avg(model_name, model, pole_word_1, pole_word_2, k)
	lex_vec = model.wv.get_vector(lex)
	sim_cos = 1 - spatial.distance.cosine(lex_vec, sem_axis)
	return sim_cos

# %% ../nbs/03_embeddings.ipynb 39
def get_axis_sims(lexs: list, models: dict, pole_words: list, k=10):
	sims = []
	for lex in lexs:
		for name, model in models.items():
			sim = {}
			sim['model'] = name
			sim['lex'] = lex
			sim['sim'] = get_axis_sim(lex, pole_words[0], pole_words[1], name, model, k)
			sims.append(sim)
	sims_df = pd.DataFrame(sims)
	return sims_df

# %% ../nbs/03_embeddings.ipynb 41
def aggregate_proj_sims(proj_sims):
	proj_sims = (proj_sims
		.pivot(index='lex', columns='model', values='sim')
		.assign(SimDiff = lambda df: df['Coronavirus'] - df['conspiracy'])
		.sort_values('SimDiff', ascending=False)
		.reset_index()
	)
	return proj_sims

# %% ../nbs/03_embeddings.ipynb 44
def plot_sem_axis(proj_sims_melted: pd.DataFrame, pole_words: list):
    chart = alt.Chart(proj_sims_melted).mark_line(point=True).encode(
        x=alt.X('SemSim', title='Semantic Similarity'),
        y=alt.Y('lex', title='', sort=alt.SortField("SimDiff")),
        color=alt.Color('model', legend=alt.Legend(title='Community', orient='top'))
    )

    text_min = alt.Chart(proj_sims_melted).mark_text(dx=-20, dy=170, color='black').encode(
        x=alt.X('min(SemSim)', title=''),
        text=alt.value(pole_words[1])
    )

    text_max = alt.Chart(proj_sims_melted).mark_text(dx=-10, dy=170, color='black').encode(
        x=alt.X('max(SemSim)', title=''),
        text=alt.value(pole_words[0])
    )

    return chart + text_min + text_max

# %% ../nbs/03_embeddings.ipynb 49
def get_nbs_vecs(lex: str, model_name: str, model: Word2Vec, k=50):
	lex_vecs = []
	lex_d = {}
	lex_d['lex'] = lex
	lex_d['type'] = 'center'
	lex_d['subreddit'] = model_name
	lex_d['vec'] = model.wv.get_vector(lex)
	lex_vecs.append(lex_d)
	for nb, sim in model.wv.most_similar(lex, topn=k):
		lex_d = {}
		lex_d['lex'] = nb
		lex_d['type'] = 'nb'
		lex_d['sim'] = sim
		lex_d['subreddit'] = model_name
		lex_d['vec'] =  model.wv.get_vector(nb)
		lex_d['freq'] = model.wv.get_vecattr(nb, "count")
		lex_vecs.append(lex_d)
	lex_vecs_df = pd.DataFrame(lex_vecs)
	return lex_vecs_df

# %% ../nbs/03_embeddings.ipynb 53
def dim_red_nbs_vecs(nbs_vecs: pd.DataFrame, perplexity=50, n_iter=1000):
    Y_tsne = TSNE(
            perplexity=perplexity,
            method='exact',
            init='pca',
            verbose=False,
            learning_rate='auto',
            n_iter=n_iter
        ).fit_transform(np.array(list(nbs_vecs['vec'])))
    nbs_vecs['x_tsne'] = Y_tsne[:, [0]]
    nbs_vecs['y_tsne'] = Y_tsne[:, [1]]
    return nbs_vecs
