# ကိုယ့်စက်မှာ Run လုပ်နည်း

## လိုအပ်ချက်

Python 3.12 သို့မဟုတ် အသစ်တစ်ခုကို install လုပ်ထားပါ။ ပထမဆုံး run လုပ်ချိန်တွင် Python package များ download လုပ်ရန် internet လိုအပ်ပါသည်။

Dependency အားလုံးကို Python 3.12 နှင့်အထက်တွင် wheel ရှိသော version များဖြင့် သတ်မှတ်ထားသဖြင့် C compiler မလိုအပ်ပါ။ pip cache နှင့် ယာဉ်ကူးစာရင်းတွေကို project folder ထဲ (`.pip-cache`, `.tmp`) မှာ သိမ်းဆည်းထားသဖြင့် C drive ပင်ပြည့်နေသောလည်း install မပျက်စေပါ။

## စတင်ရန်

1. Project ZIP ကို extract လုပ်ပါ။
2. **Windows:** folder ထဲရှိ `run_local.bat` ကိုဖွင့်ပါ။ **macOS/Linux:** Terminal မှ project folder ထဲဝင်ပြီး `bash run_local.sh` ကို run ပါ။
3. Script သည် `.venv` ဖန်တီးပြီး dependency များ install လုပ်ကာ `.env` local settings ဖိုင်ကို ပြင်ဆင်ပေးပါမည်။ ပထမဆုံးအကြိမ်တွင် admin username (`admin`) နှင့် random password ကို terminal ထဲတွင် တစ်ကြိမ်ပြပါမည်။ Password ကို မမေ့စေရန် `.env` ထဲတွင်လည်း သိမ်းထားပါသည်။
4. Browser တွင် `http://127.0.0.1:3000` ဖွင့်ပြီး ထို username/password ဖြင့် login ဝင်ပါ။
5. CSV တင်သွင်းမှုကို စမ်းရန် folder ထဲရှိ `sample_inflow_dataset.csv` ကို ရွေးပြီး dashboard ၏ **Load Dataset** ခလုတ်မှ upload လုပ်ပါ။ ဒီဖိုင်က synthetic data ဖြစ်ပြီး တကယ့် dam telemetry မဟုတ်ပါ။
6. **LSTM**, **GRU** သို့မဟုတ် **RGF-LSTM** ကိုနှိပ်ပါ။ Model run ပြီးလျှင် actual-vs-predicted chart၊ forecast table၊ performance metrics နှင့် scatter plot ပါသော သက်ဆိုင်ရာ results page ပွင့်ပါမည်။ **Back** ဖြင့် dashboard သို့ ပြန်နိုင်ပါသည်။
7. Server ပိတ်ရန် terminal တွင် `Ctrl+C` နှိပ်ပါ။ နောက်တစ်ကြိမ်တွင် launcher ကို ပြန်ဖွင့်ရုံဖြင့် ရပါသည်။

## Local data နှင့် login

Local run သည် Managed MySQL အစား `data/local.db` ထဲရှိ SQLite ကို အသုံးပြုသည်။ Dataset နှင့် forecast history များကို ကိုယ့်စက်ပေါ်တွင်သာ သိမ်းပါသည်။ `.env` ကို source control သို့မဟုတ် အခြားသူများထံ မမျှဝေပါနှင့်။ Password ပျောက်သွားပါက `.env` ထဲရှိ `LOCAL_ADMIN_PASSWORD` ကို ပြင်ပြီး app ကိုပြန်စတင်နိုင်ပါသည်။

ဒီ local username/password login သည် `APP_MODE=local` ဖြင့် `localhost` အတွက်သာဖြစ်ပြီး hosted site တွင် မသုံးပါ။ Hosted version က Manus OAuth ကို ဆက်သုံးသည်။ Local development server ကို internet/LAN ပေါ်သို့ ဖွင့်မထားပါနှင့်။

Port 3000 ကို အခြား app တစ်ခုအသုံးပြုနေပါက `run_local.sh` သို့မဟုတ် `run_local.bat` ထဲရှိ port နှင့် `.env` ရှိ `APP_ALLOWED_ORIGINS` ကို port အသစ်နှင့် တူညီအောင် ပြောင်းပါ။
