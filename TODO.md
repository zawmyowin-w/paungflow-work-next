# TODO

## Login နှင့် admin access
- [x] Dashboard ရှေ့တွင် login page ပြရမည်။ Login မဝင်ရသေးသူသည် dashboard ကို မကြည့်နိုင်ရ၊ authenticated session အောင်မြင်မှသာ ဝင်ရောက်နိုင်ရမည်။
- [x] Login session ကို လုံခြုံစွာထိန်းသိမ်းပြီး logout လုပ်နိုင်ရမည်။
- [x] State ပြောင်းလဲစေသော logout နှင့် dataset/forecast requests များတွင် browser origin ကို အတည်ပြုပြီး cross-site requests များကို ပယ်ချရမည်။

## Light mode နှင့် dark mode
- [x] Light mode နှင့် dark mode နှစ်မျိုးလုံး ပါရမည်။
- [x] အသုံးပြုသူသည် mode နှစ်မျိုးအကြား ပြောင်းနိုင်ပြီး ရွေးထားသည့် mode ကို နောက်တစ်ကြိမ်ဝင်သောအခါလည်း ထိန်းသိမ်းရမည်။

## Dataset တင်သွင်းခြင်းနှင့် စစ်ဆေးခြင်း
- [x] Load Dataset မှ CSV သို့မဟုတ် သင့်လျော်သော time-series dataset ကို တင်သွင်း၊ စစ်ဆေးပြီး အကျဉ်းချုပ်ကြည့်ရှုနိုင်ရမည်။
- [x] Dataset မရှိခြင်း၊ format မမှန်ခြင်း သို့မဟုတ် required time-series values မပြည့်စုံခြင်းကို အသုံးပြုသူနားလည်နိုင်သော အခြေအနေဖြင့် ပြရမည်။
- [x] CSV time values များသည် ISO 8601 format ဖြစ်ပြီး unique၊ strictly increasing ဖြစ်ရမည်။ CSV dataset နှင့် forecast runs များကို authenticated admin နှင့် browser origin scope အလိုက် ခွဲထားရမည်။
- [x] Dashboard comparison rows နှင့် model status သည် လက်ရှိ dataset ၏ forecast runs များကိုသာ ပြရမည်။
- [x] `sample_inflow_dataset.csv` တွင် upload schema နှင့်ကိုက်ညီသော 2024 synthetic daily inflow sample ပါဝင်ပြီး၊ တကယ့် dam telemetry မဟုတ်ကြောင်း ရှင်းလင်းရမည်။

## Forecast မော်ဒယ်များ
- [ ] LSTM ကို ရွေးချယ်ပြီး dam inflow forecast run လုပ်ကာ ခန့်မှန်းရလဒ် ပြသနိုင်ရမည်။
- [ ] GRU ကို ရွေးချယ်ပြီး dam inflow forecast run လုပ်ကာ ခန့်မှန်းရလဒ် ပြသနိုင်ရမည်။
- [ ] RGF-LSTM ကို ရွေးချယ်ပြီး dam inflow forecast run လုပ်ကာ ခန့်မှန်းရလဒ် ပြသနိုင်ရမည်။
- [ ] Model သုံးမျိုး၏ forecast series နှင့် accuracy/error metrics များကို chart နှင့် summary ဖြင့် နှိုင်းယှဉ်နိုင်ရမည်။

**Status note:** Forecast controls and comparison UI are wired to transparent rolling-baseline preview adapters. No trained LSTM/GRU/RGF-LSTM weights or validated dam telemetry were supplied, so the neural-model acceptance items remain open; replace the adapters with validated model weights before operational use.

## Dam location, information နှင့် key indicators
- [x] Lower Paung-Luang Dam ၏တည်နေရာကို marker ပါသော interactive map panel တွင် ပြသရမည်။
- [x] Dam information panel တွင် အမည်၊ တည်နေရာ၊ စွမ်းရည်နှင့် သက်ဆိုင်ရာ အခြေခံအချက်အလက်များ ပါရမည်။
- [x] Key Features panels တွင် လက်ရှိ inflow၊ forecast horizon၊ dataset status နှင့် model status ကဲ့သို့ အဓိက dashboard indicators များ ပြသရမည်။
- [x] Dashboard ၏ layout နှင့် content ကို ပူးတွဲ reference ပုံ၏ data-dense control-panel ပုံစံအတိုင်း စီစဉ်ရမည်။
- [x] Python ကို အသုံးပြုပြီး dashboard ကို တည်ဆောက်ရမည်။

## Local installation
- [x] Windows နှင့် macOS/Linux တွင် setup script များဖြင့် Python environment နှင့် dependencies တည်ဆောက်ကာ `127.0.0.1:3000` တွင် app ကို run လုပ်နိုင်ရမည်။
- [x] Local mode တွင် random admin password၊ local SQLite persistence နှင့် localhost-only login သုံးရမည်။ Hosted site တွင် Manus OAuth ကို ဆက်သုံးရမည်။

## Model prediction results page
- [x] LSTM ကိုနှိပ်သည့်အခါ ပူးတွဲပေးထားသော prediction-results ပုံစံဖြင့် ရလဒ်စာမျက်နှာ သီးသန့်ဖွင့်ရမည်။ GRU နှင့် RGF-LSTM တွင်လည်း သက်ဆိုင်ရာ model အမည်နှင့် ရလဒ်ကို ပြသရမည်။
- [x] ရလဒ်စာမျက်နှာတွင် actual နှင့် predicted inflow chart၊ ရွေးထားသော horizon အတွက် နောက်လာမည့် forecast table၊ performance metrics နှင့် actual-vs-predicted scatter plot ပါရမည်။
- [x] Page မှ dashboard သို့ ပြန်နိုင်ရမည်၊ အသုံးပြုသူ authentication၊ dataset ownership/origin scope နှင့် light/dark theme ကို ထိန်းသိမ်းရမည်။

## Code quality (clean code refactor)
- [x] Backend ကို layer အလိုက် ပြန်ဖွဲ့ရမည်။ `app/api` → `app/services` → `app/domain` → `app/db` ဖြင့် dependency တို့ကို အတွင်းသို့သာ လှည့်စေရမည်။
- [x] Domain အပိုင်းကို I/O မလုပ်ဘဲ pure Python အဖြစ် ပြုလုပ်ရမည်။
- [x] Environment configuration ကို `app/config.py` တစ်နေရာတည်းတွင် စုစည်းရမည်။
- [x] Business error များကို typed error hierarchy ဖြင့် ရေးပြီး API layer မှာသာ HTTP status အဖြစ် ပြောင်းလဲရမည်။
- [x] Request/response ကို Pydantic model များဖြင့် သတ်မှတ်ရမည်။
- [x] `pytest` test suite၊ `ruff` lint/format နှင့် `mypy` type check ကို `pyproject.toml` ဖြင့် သတ်မှတ်ရမည်။
- [x] Front end အားလုံးကို Python ဖြင့် ရေးရမည်။ HTML = Jinja2 template (`templates/`)၊ CSS = Python module (`app/web/assets/`)၊ chart = server-side SVG (`app/web/charts.py`)၊ action များ = plain HTML form။
- [x] Browser JavaScript ကို header clock ticker တစ်ခုတည်းသာ ကျန်ရှိရမည်။ Theme ကို cookie + POST form ဖြင့်၊ map zoom ကို CSS `:checked` ဖြင့် လုပ်ရမည်။
