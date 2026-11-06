import gzip, io, shutil
import numpy as np
import pytest
from experiments.e8_cpu_static_embedding import build_idf, encode_text, rank_embeddings, rank_embeddings_checkpointed, tokenize, download_pretrained_model, load_pretrained_model

class FakeFastText:
    def get_word_vector(self, word):
        table = {'search':[1,0,0], 'customer':[0,1,0], 'invoice':[0,0,1], 'unseen_api':[1,1,0]}
        return np.asarray(table.get(word,[.1,.1,.1]),dtype=np.float32)

def test_tokenizer(): assert tokenize('Search Customer_ID APIv2') == ['search','customer_id','apiv2']
def test_idf_tool_corpus_smoothed():
    idf,n=build_idf(['search customer','search invoice']); assert n==2; assert idf['search']==pytest.approx(1.0); assert idf['customer']==pytest.approx(np.log(3/2)+1)
def test_weighted_pooling_unit_norm():
    v,s=encode_text('search customer',FakeFastText(),{'search':1,'customer':2},3); assert np.linalg.norm(v)==pytest.approx(1); assert v[1]>v[0]; assert s['zero_vector']==0
def test_oov_uses_fasttext_vector_api():
    v,s=encode_text('unseen_api',FakeFastText(),{},3); assert np.linalg.norm(v)==pytest.approx(1); assert s['zero_vector']==0
def test_empty_query_abstains():
    v,s=encode_text('!!!',FakeFastText(),{},3); assert np.array_equal(v,np.zeros(3,dtype=np.float32)); assert s['zero_vector']==1
def test_cosine_stable_tie_and_zero_abstention():
    q=np.asarray([[1,0,0],[0,0,0]],dtype=np.float32); d=np.asarray([[0,1,0],[1,0,0]],dtype=np.float32); assert rank_embeddings(q,d,['b','a'],2)==[['a','b'],[]]
def test_rank_rejects_invalid_inputs():
    with pytest.raises(ValueError,match='dimensions'): rank_embeddings(np.ones((1,2)),np.ones((1,3)),['x'])
    with pytest.raises(ValueError,match='non-finite'): rank_embeddings(np.asarray([[np.nan]]),np.ones((1,1)),['x'])
def test_checkpoint_resume_and_fingerprint(tmp_path):
    q=np.asarray([[1,0],[0,1],[1,1]],dtype=np.float32); d=np.asarray([[1,0],[0,1]],dtype=np.float32); ids=['a','b']; tasks=['q1','q2','q3']
    first=rank_embeddings_checkpointed(q,d,ids,tasks,tmp_path,'fp',2,2); second=rank_embeddings_checkpointed(q,d,ids,tasks,tmp_path,'fp',2,2); assert first==second
    with pytest.raises(ValueError,match='fingerprint mismatch'): rank_embeddings_checkpointed(q,d,ids,tasks,tmp_path,'changed',2,2)
def test_streamed_gzip_download_and_hash(tmp_path,monkeypatch):
    payload=b'x'*(1024*1024+10); compressed=io.BytesIO()
    with gzip.GzipFile(fileobj=compressed,mode='wb') as f: f.write(payload)
    class Response(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self,*args): self.close()
    monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k: Response(compressed.getvalue()))
    monkeypatch.setattr('shutil.disk_usage',lambda p: shutil._ntuple_diskusage(20 * 1024**3, 1 * 1024**3, 19 * 1024**3))
    meta=download_pretrained_model(tmp_path/'cc.en.300.bin','https://example.invalid/model.gz',8)
    assert (tmp_path/'cc.en.300.bin').read_bytes()==payload and meta['bytes']==len(payload) and len(meta['sha256'])==64
def test_download_fails_closed_on_low_disk(tmp_path,monkeypatch):
    monkeypatch.setattr('shutil.disk_usage',lambda p: shutil._ntuple_diskusage(10,9,1))
    with pytest.raises(RuntimeError,match='Insufficient free disk'): download_pretrained_model(tmp_path/'model.bin','https://example.invalid/model.gz',8)
def test_load_model_validates_dimension(monkeypatch,tmp_path):
    import sys
    class M:
        def get_dimension(self): return 300
    class F:
        @staticmethod
        def load_model(path): return M()
    monkeypatch.setitem(sys.modules,'fasttext',F()); p=tmp_path/'m.bin'; p.write_bytes(b'x'); assert load_pretrained_model(p).get_dimension()==300
def test_no_training_entrypoint():
    import experiments.e8_cpu_static_embedding as module; assert not hasattr(module,'train_fasttext')
