import logging
from types import SimpleNamespace

import wandb
from langchain.chains import ConversationalRetrievalChain
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma
from prompts import load_chat_prompt
from wandb.integration.langchain import WandbTracer

logger = logging.getLogger(__name__)


def load_vector_store(wandb_run: wandb.run, openai_api_key: str) -> Chroma:
    """Load a vector store from a Weights & Biases artifact
    Args:
        run (wandb.run): An active Weights & Biases run
    Returns:
        Chroma: A chroma vector store object
    """
    # load vector store artifact
    vector_store_artifact_dir = wandb_run.use_artifact(
        wandb_run.config.vector_store_artifact, type="search_index"
    ).download()
    embedding_fn = OpenAIEmbeddings(openai_api_key=openai_api_key)
    # load vector store
    vector_store = Chroma(
        embedding_function=embedding_fn, persist_directory=vector_store_artifact_dir
    )

    return vector_store


def load_chain(wandb_run: wandb.run, vector_store: Chroma, openai_api_key: str):
    """Load a ConversationalQA chain from a config and a vector store

    Args:
        config (SimpleNamespace): A config object

    """
    retriever = vector_store.as_retriever()
    llm = ChatOpenAI(
        openai_api_key=openai_api_key,
        model_name=wandb_run.config.model_name,
        temperature=wandb_run.config.chat_temperature,
        max_retries=wandb_run.config.max_fallback_retries,
    )
    chat_prompt_dir = wandb_run.use_artifact(
        wandb_run.config.chat_prompt_artifact, type="prompt"
    ).download()
    qa_prompt = load_chat_prompt(f"{chat_prompt_dir}/prompt.json")
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        combine_docs_chain_kwargs={"prompt": qa_prompt},
        return_source_documents=True,
    )
    return qa_chain


def get_answer(
    chain: ConversationalRetrievalChain,
    callback: WandbTracer,
    question: str,
    chat_history: list[tuple[str, str]],
):
    result = chain(
        inputs={"question": question, "chat_history": chat_history},
        callbacks=[callback],
        return_only_outputs=True,
    )
    response = f"Answer:\t{result['answer']}"
    return response
