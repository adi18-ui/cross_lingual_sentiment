# -*- coding: utf-8 -*-
"""cross_lingual_transfer.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1obkjVQrDJ7rzAi_JKNtX1ZnQWE96g5YZ

# **Installing Dependecies**
"""

!pip install datasets

"""# **Importing Libraries**"""

import pandas as pd
import re
import ast
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm
import time
from sklearn.utils import shuffle
from sklearn.metrics import accuracy_score

# check for gpu
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(device)

"""# **Loading the Dataset**"""

from datasets import load_dataset

ds = load_dataset("stanfordnlp/sst2")

print(ds)

train_df = ds['train'].to_pandas()
test_df = ds['test'].to_pandas()
valid_df = ds['validation'].to_pandas()

train_df.head()

train_df = train_df[:-10000]

print(train_df.shape)
print(test_df.shape)
print(valid_df.shape)

"""# **Custom Dataset**"""

import torch
from torch.utils.data import Dataset

class MyDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_length):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        text = self.texts[idx]
        label = self.labels[idx]

        # Tokenizing text
        encoding = self.tokenizer(
            text,
            padding='max_length',
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt"
        )

        input_ids = encoding["input_ids"].squeeze(0)
        attention_mask = encoding["attention_mask"].squeeze(0)

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": torch.tensor(label, dtype=torch.long)
        }

# Conversion to list for easier processing
train_text = train_df['sentence'].tolist()
train_label = train_df['label'].tolist()

valid_text = valid_df['sentence'].tolist()
valid_label = valid_df['label'].tolist()

test_text = test_df['sentence'].tolist()
test_label = test_df['label'].tolist()

from transformers import AutoTokenizer, AutoModelForSequenceClassification
from transformers import XLMRobertaTokenizer, XLMRobertaForSequenceClassification
from transformers import TrainingArguments, Trainer

tokenizer = XLMRobertaTokenizer.from_pretrained("xlm-roberta-base")

max_length = 48

train_dataset = MyDataset(train_text, train_label, tokenizer, max_length)

valid_dataset = MyDataset(valid_text, valid_label, tokenizer, max_length)

test_dataset = MyDataset(test_text, test_label, tokenizer, max_length)

train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True)


for batch in train_loader:
    print(batch)
    break

valid_loader = DataLoader(valid_dataset, batch_size=8, shuffle=False)

test_loader = DataLoader(test_dataset, batch_size=8, shuffle=False)

from torch.optim import Adam
from transformers import get_scheduler

"""# **Defining the Model**"""

model = AutoModelForSequenceClassification.from_pretrained("xlm-roberta-base", num_labels=2)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

"""# **Setting Parameters**"""

optimizer = Adam(model.parameters(), lr=2e-5)
num_epochs = 5
num_training_steps = num_epochs * len(train_loader)
lr_scheduler = get_scheduler("linear", optimizer=optimizer, num_warmup_steps=0, num_training_steps=num_training_steps)
loss_fn = torch.nn.CrossEntropyLoss()

"""# **Training the model**"""

# Training Loop
for epoch in range(num_epochs):
    model.train()
    total_loss = 0
    start_time = time.time()

    for batch in tqdm(train_loader, desc=f"Epoch {epoch + 1}/{num_epochs}", unit="batch"):
        optimizer.zero_grad()

        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["labels"].to(device)

        outputs = model(input_ids=input_ids, attention_mask=attention_mask, labels=labels)
        loss = outputs.loss
        total_loss += loss.item()

        loss.backward()
        optimizer.step()
        lr_scheduler.step()

    end_time = time.time()
    epoch_time = end_time - start_time

    avg_train_loss = total_loss / len(train_loader)
    print(f"Epoch {epoch+1}: Train Loss = {avg_train_loss:.4f}, Time: {epoch_time:.2f} seconds")

    model.eval()
    correct = 0
    total = 0
    with torch.no_grad():
        for batch in tqdm(valid_loader, desc="Validation", unit="batch"):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            predictions = torch.argmax(outputs.logits, dim=-1)

            correct += (predictions == labels).sum().item()
            total += labels.size(0)

    accuracy = correct / total
    print(f"Epoch {epoch+1}: Validation Accuracy = {accuracy:.4f}")

"""# **Preparing Hindi Dataset**"""

with open("neg_train.txt", "r", encoding="utf-8") as f:
    sentences = [line.strip() for line in f if line.strip()]

neg_label = [0] * len(sentences)

df_neg = pd.DataFrame({
    "sentence": sentences,
    "label": neg_label
})

df_neg.head()

with open("pos_train.txt", "r", encoding="utf-8") as f:
    sentences = [line.strip() for line in f if line.strip()]

pos_label = [1] * len(sentences)

df_pos = pd.DataFrame({
    "sentence": sentences,
    "label": pos_label
})

df_pos.head()

hindi_df = pd.concat([df_pos, df_neg], ignore_index=True)
hindi_df = shuffle(hindi_df, random_state=42)

hindi_df.head()

hindi_df.shape

hindi_texts = hindi_df['sentence'].tolist()
hindi_labels = hindi_df['label'].tolist()

hindi_dataset = MyDataset(hindi_texts, hindi_labels, tokenizer, max_length)

hindi_loader = DataLoader(hindi_dataset, batch_size=8, shuffle=False)

"""# **Making Prediction on Hindi Dataset**"""

all_predictions = []
all_labels = []

model.eval()
with torch.no_grad():
    for batch in tqdm(hindi_loader, desc="Predicting on Hindi Dataset"):
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["labels"].to(device)

        outputs = model(input_ids=input_ids, attention_mask=attention_mask)
        predictions = torch.argmax(outputs.logits, dim=-1)

        all_predictions.extend(predictions.cpu().numpy())
        all_labels.extend(labels.cpu().numpy())


accuracy = accuracy_score(all_labels, all_predictions)
print(f"Accuracy on Hindi Dataset: {accuracy:.4f}")

"""# **Saving the Model**"""

model.save_pretrained("./sentiment_model")
tokenizer.save_pretrained("./sentiment_tokenizer")

