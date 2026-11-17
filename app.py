import concurrent.futures
import re
import time
import urllib.request
from flask import Flask, render_template_string

app = Flask(__name__)

# ==========================================
# আপনার নম্বর এবং লিংকের তালিকা এখানে সরাসরি দিন
# ==========================================
data_list = [
    (
        "+13082573334",
        "http://169.58.215.134:11111/sms/wa-dQ85Bqbru9-9rts-CwhK-zfSEPQYpqFq/6",
    ),
    (
        "+15177144880",
        "http://169.58.215.134:11111/sms/wa-nd7K_z2Re19orVDJTpFFZfNNUMEIzEs2/6",
    ),
    (
        "+19717777024",
        "http://169.58.215.134:11111/sms/wa-sBImpwBbyiiGxIsTzgl2KIB6fOvJK2nJ/6",
    ),
    (
        "+15853004453",
        "http://169.58.215.134:11111/sms/wa-fmlhskEwV94MOV1cXvgG60H-6w1NLAA-/6",
    ),
    (
        "+19592143777",
        "http://169.58.215.134:11111/sms/wa-sguLHw24TEx_-Tv8SubNAlBDDP4Y9uUN/6",
    ),
    (
        "+18153103733",
        "http://169.58.215.134:11111/sms/wa-tRPnrt6VUnMsvcGlGyVhAS1BvkerUEUr/6",
    ),
    (
        "+15082051859",
        "http://169.58.215.134:11111/sms/wa-yWJW_To00HbHMDHFiQKPdZIw98kHGYbj/6",
    ),
    (
        "+13345814820",
        "http://169.58.215.134:11111/sms/wa-u19MD_LFLD5echJMAW_-GMNMbG-iMTr3/6",
    ),
]


def check_single_otp(index, phone, url):
  start_time = time.time()
  try:
    base_parts = url.split("/sms/")
    api_url = base_parts[0] + "/api/sms/" + base_parts[1]
  except Exception:
    return index, phone, None, False

  while time.time() - start_time < 5:
    try:
      req = urllib.request.Request(
          api_url, headers={"User-Agent": "Mozilla/5.0"}
      )
      with urllib.request.urlopen(req, timeout=3) as response:
        content = response.read().decode("utf-8").strip()
        match = re.search(r"\b\d{5,6}\b", content)
        if match:
          return index, phone, match.group(0), True
    except Exception:
      pass
    time.sleep(1)

  return index, phone, None, False


# HTML ডিজাইন (যাতে ব্রাউজারে বা Render-এ লাইভ স্ট্যাটাস সুন্দর দেখায়)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>REX Number & OTP Checker</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 20px; }
        .container { max-width: 600px; margin: auto; background: #1e293b; padding: 20px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }
        h2 { text-align: center; color: #38bdf8; }
        .stats { display: flex; justify-content: space-around; background: #334155; padding: 10px; border-radius: 5px; margin-bottom: 20px; font-weight: bold; }
        ul { list-style: none; padding: 0; }
        li { background: #334155; margin-bottom: 8px; padding: 10px 15px; border-radius: 5px; display: flex; justify-content: space-between; align-items: center; }
        .success { color: #4ade80; font-weight: bold; }
        .failed { color: #f87171; }
        .btn { display: block; width: 100%; background: #0284c7; color: white; border: none; padding: 10px; font-size: 16px; border-radius: 5px; cursor: pointer; text-align: center; text-decoration: none; margin-top: 15px; }
        .btn:hover { background: #0369a1; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🚀 REX OTP Checker</h2>
        <div class="stats">
            <div>✅ Received: {{ received }}</div>
            <div>❌ Failed: {{ failed }}</div>
            <div>📦 Total: {{ total }}</div>
        </div>
        <ul>
            {% for item in results %}
                <li>
                    <span>{{ item.index }}. 📱 {{ item.phone }}</span>
                    {% if item.otp %}
                        <span class="success">✅ {{ item.otp }}</span>
                    {% else %}
                        <span class="failed">❌ নাই</span>
                    {% endif %}
                </li>
            {% endfor %}
        </ul>
        <a href="/" class="btn">🔄 Refresh / Re-check</a>
    </div>
</body>
</html>
"""


@app.route("/")
def index():
  total_links = len(data_list)
  results_data = [None] * total_links
  received_count = 0
  failed_count = 0

  # মাল্টিথ্রেডিং দিয়ে খুব দ্রুত সব চেক করা
  with concurrent.futures.ThreadPoolExecutor(
      max_workers=min(10, total_links)
  ) as executor:
    futures = [
        executor.submit(check_single_otp, i, phone, url)
        for i, (phone, url) in enumerate(data_list, start=1)
    ]

    for future in concurrent.futures.as_completed(futures):
      idx, phone, otp, success = future.result()
      results_data[idx - 1] = {
          "index": idx,
          "phone": phone,
          "otp": otp,
          "success": success,
      }
      if success:
        received_count += 1
      else:
        failed_count += 1

  return render_template_string(
      HTML_TEMPLATE,
      results=results_data,
      received=received_count,
      failed=failed_count,
      total=total_links,
  )


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000)
