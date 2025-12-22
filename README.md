# 📰 Greek News AI Digest v2

![alt text](GRnewsAI_image.jpeg?raw=true)

Python3.9+ script το οποίο ανακτά άρθρα από RSS feed που καθορίζονται από τον χρήστη, τα ομαδοποιεί με βάση τη θεματολογία τους (χρησιμοποιώντας το "ελαφρύ" LLM Gemma3) και ακολούθως παράγει τοπικά χρησιμοποιώντας το LLM [Llama Krikri](https://arxiv.org/abs/2505.13772) (μέσω Ollama ή LMStudio) ένα συνθετικό σύντομο δελτίο ειδήσεων σε PDF, Markdown, HTML format και σε MP3 audio στα ελληνικά για προσωπική χρήση. Στο τελικό δελτίο περιέχονται και τα links των πηγών του κάθε θέματος. Αποτελεί ευθύνη του χρήστη ο σεβασμός των κανόνων πνευματικής ιδιοκτησίας των πηγών που χρησιμοποιεί. Ο κώδικας αποτελεί εξέλιξη της [πρώτης έκδοσης του GRNewsAI](https://github.com/alexandros-koutsioumpas/GRNewsAI/) και σε αυτό το στάδιο αποτελεί ένα πείραμα για το πως μπορεί κάποιος τοπικά στο μηχάνημα του (άρα με ασφάλεια και κόστος μόνο την ενέργεια που καταναλώνει η GPU/CPU) να χρησιμοποιεί μεγάλα γλωσσικά μοντέλα για τη "διύλιση" πληροφορίας.

---

## 📦 Εγκατάσταση

1. **Clone repository:**
   ```bash
   git clone https://github.com/alexandros-koutsioumpas/GRNewsAIv2.git
   cd GRNewsAIv2
   ```

2. **Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Εγκατάσταση Ollama (αν δεν είναι ήδη εγκατεστημένο):**
   Οδηγίες εδώ https://ollama.com

   ακολούθως

   ```bash
   ollama pull ilsp/llama-krikri-8b-instruct:latest
   ollama pull gemma3:4b
   ```

   εναλλακτικά εγκατάσταση **LMStudio**, των μοντέλων `llama-krikri`/`gemma4b` και μεταβολή της μεταβλητής `ENGINE = 'LMStudio'`. (Merci [T. Kleisas](https://github.com/tkleisas)!)
   
5. Σε ορισμένους υπολογιστές χρειάζεται να "τρέξετε" το `Python Install Certificates script` (στο `MacOS` θα το βρείτε στο `Applications/Python/Install Certificates.command`)

---

## 📄 feeds_gr.yaml το αρχείο περιέχει τα RSS feeds

Οι πηγές RSS στο αρχείο είναι ενδεικτικές, μπορείτε να προσθέσετε/αφαιρέσετε RSS links. Με `#` στην αρχή της γραμμής η πηγή θα αγνοηθεί. **Πριν την πρώτη εκτέλεση του script** ο χρήστης οφείλει να διαμορφώσει το αρχείο με τις πηγές που επιθυμεί (τρεις πηγές κατ'ελάχιστο).

```yaml
feeds:
#  - "https://www.tanea.gr/feed/"
#  - "https://www.tovima.gr/feed/"
#  - "https://www.news.gr/rss.ashx"
#  - "https://www.902.gr/feed/featured"
#  - "https://www.newsbomb.gr/oles-oi-eidhseis?format=feed&type=rss"
#  - "https://www.protagon.gr/feed"
```

Αν ο κώδικας αργεί στο μηχάνημα σας, αφαιρέστε πηγές.

---

## 🚀 Εκτέλεση του Script

αφού έχετε κατάλληλα διαμορφώσει το αρχείο `feeds_gr.yaml`

```bash
python GRNewsAIv2.py
```

Το script θα:
- Ανακτήσει 25 άρθρα ανα feed
- θα ομαδοποιήσει συναφή θέματα
- θα τα συνοψίσει
- θα παράγει ένα δελτίο σε μορφή markdown, pdf, html document και mp3 audio

---

## 🗣️ Ρυθμίσεις

**Για τη ρύθμιση μοντέλου, μεταβλητή `BROADCAST_MODEL`**

- `ilsp/llama-krikri-8b-instruct:latest` (default)


**Για τη ρύθμιση ollama/LMStudio, μεταβλητή `ENGINE`**

- `ollama` (default)
- `LMStudio`

**Για τη ρύθμιση αριθμού θεμάτων στο δελτίο, μεταβλητή `NUM_STORIES`**

- `7` (default)

**Για τη ρύθμιση αριθμού άρθρων ανα feed, μεταβλητή `NUM_ARTICLES`**

- `25` (default)

**Για τη ρύθμιση φωνής, μεταβλητή `TTS_VOICE`**

- `el-GR-NestorasNeural` (default, ανδρική)
- `el-GR-AthinaNeural` (γυναικεία)


---

## 🗣️ Περιοδική εκτέλεση του script 

Μπορείτε αυτόματα να εκτελείτε το script περιοδικά κάθε x ώρες δίνοντας των αριθμό των ωρών ως ακέραιο command line argument, π.χ. για εκτέλεση καθε 8 ώρες:

```bash
python GRNewsAIv2.py 8
```

παράλληλα εκτελώντας το script σε ένα synced cloud folder (Dropbox/iCloud/GoogleDrive) έχετε διαθέσιμο το δελτίο για αναπαραγωγή και σε mobile συσκευές για ανάγνωση/ακρόαση στο μετρό ή στο αυτοκίνητο.

---

## 🧠 Tips

 - Με 10 RSS feed και `max_articles=25` σε ένα M4 MacBook Pro η παραγωγή του δελτίου διαρκεί ~50min. Με 3 RSS feed στο ίδιο μηχάνημα η παραγωγή του δελτίου διαρκεί ~10min. Γενικά σε PC που δεν έχουν GPU και VRAM αρκετή για να "σηκώσει" το Llama KriKri αναμένεται το runtime να είναι αρκετά μεγαλύτερο και συνίσταται η μείωση των πηγών RSS.

- Σε PC με NVidia RTX40xx και ανάλογες GPU o κώδικας τρέχει σε λίγα λεπτά και μπορούν να χρησιμοποιηθούν ακόμα περισσότερες πηγές RSS.

- Χρησιμοποιώντας ollama ENGINE οι απαιτήσεις σε RAM ή VRAM είναι μικρές, γύρω στα 6Gb.


---

## 🔒 License

MIT License
