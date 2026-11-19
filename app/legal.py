"""What the law says about each rule, and where the worker can go next.

Plain-Bangla legal INFORMATION, not advice. Compiled from news and NGO summaries of the
Overseas Employment and Migrants Act 2013 (OEMA) and official helplines; a legal team will
review every line after the preliminary round. Keep sources in LEGAL_SOURCES up to date.
"""
from .schema import Flag

HELP_HOME = "প্রবাসবন্ধু কল সেন্টার ১৬১৩৫ (টোল ফ্রি, ২৪ ঘণ্টা)"
HELP_ABROAD = "বিদেশ থেকে +৮৮০৯৬১০১০২০৩০"
LEGAL_AID = "সরকারি বিনা খরচে আইনি সহায়তা: লিগ্যাল এইড ১৬৬৯৯"

FALSE_PROMISE = ("মিথ্যা প্রতিশ্রুতি বা বেতন-সুবিধার মিথ্যা আশ্বাস দিয়ে টাকা নেওয়া বৈদেশিক কর্মসংস্থান ও অভিবাসী আইন ২০১৩-এর "
                 "ধারা ৩১-এ শাস্তিযোগ্য অপরাধ (৫ বছর পর্যন্ত কারাদণ্ড ও জরিমানা)। ক্ষতিপূরণের জন্য ধারা ২৮-এ মামলা করা যায়।")

LEGAL = {
    "R01": (FALSE_PROMISE, f"টাকা দেওয়া বন্ধ রাখুন, কাগজ ও রসিদ রাখুন। {HELP_HOME}।"),
    "R02": (FALSE_PROMISE + " সৌদি আরবে নারী গৃহকর্মীদের জন্য সরকার-নির্ধারিত খরচ শূন্য টাকা।",
            f"গৃহকর্মীর ভিসায় কারখানা বা অফিসের কাজের কথা বলা হলে যাওয়ার আগে নিশ্চিত হন। {HELP_HOME}।"),
    "R03": (FALSE_PROMISE, "ডিমান্ড লেটারে নিয়োগকর্তার নাম মিলিয়ে নিন; না মিললে এজেন্সির কাছে লিখিত ব্যাখ্যা চান।"),
    "R04": (FALSE_PROMISE, "কাগজে লেখা বেতনই আইনত গণ্য হয়; মুখের কথা নয়। লিখিত চুক্তিতে প্রতিশ্রুত বেতন চান।"),
    "R05": ("সরকার প্রতিটি দেশের জন্য সর্বোচ্চ অভিবাসন খরচ ঠিক করে দেয়। বেশি নেওয়ার প্রমাণ পেলে ব্যবস্থা নেওয়ার কথা সরকার বলেছে; "
            "বিএমইটি-তে অভিযোগ করলে সালিশে টাকা ফেরত বা ক্ষতিপূরণ পাওয়া যায়।",
            f"প্রতিটি টাকার রসিদ চান। বিএমইটি বা জেলা কর্মসংস্থান ও জনশক্তি অফিসে (DEMO) অভিযোগ করুন। {HELP_HOME}।"),
    "R06": ("শুধু বিএমইটি-লাইসেন্সধারী (RL নম্বর আছে এমন) রিক্রুটিং এজেন্সি বিদেশে কর্মী পাঠাতে পারে (বৈদেশিক কর্মসংস্থান ও অভিবাসী আইন ২০১৩, অধ্যায় ৩)।",
            "সরকারি Overseas Employment Platform-এ (oep.gov.bd) RL নম্বর মিলিয়ে নিন। লাইসেন্স না থাকলে টাকা দেবেন না।"),
    "R07": ("চুক্তির মাধ্যমে অভিবাসন প্রক্রিয়া, কাজের পরিবেশ ও আইনি অধিকারের তথ্য পাওয়া আপনার অধিকার (ধারা ২২)।",
            "টাকা দেওয়ার বা বিমানে ওঠার আগে নিজের বোঝা ভাষায় লিখিত, স্বাক্ষরিত চুক্তিপত্র চান।"),
    "R08": ("এই দেশে প্রতারণা ও মানবপাচারের খবর বেশি। বাংলাদেশে মানবপাচার প্রতিরোধ ও দমন আইন ২০১২ আছে।",
            f"কাগজ সরকারি সূত্রে যাচাই না করে যাবেন না। জরুরি বিপদে ৯৯৯। {HELP_HOME}।"),
    "R09": ("মেয়াদ শেষ হওয়া ভিসায় গেলে বিদেশে অবৈধ হয়ে পড়ার ঝুঁকি থাকে।",
            "এজেন্সির কাছে নতুন বা নবায়ন করা ভিসা চান; না পেলে বিএমইটি-তে জানান।"),
    "R10": ("চুক্তির চেয়ে কম বেতন দেওয়া চুক্তিভঙ্গ। প্রতারণার শিকার কর্মীর আইনি সহায়তা পাওয়ার অধিকার আছে (ধারা ২৭)।",
            f"বেতনের স্লিপ ও চুক্তি সংরক্ষণ করুন। দূতাবাসের শ্রম কল্যাণ উইং-এ যোগাযোগ করুন। {HELP_ABROAD}।"),
    "R11": ("চুক্তিতে নেই এমন বড় কাটা চুক্তিভঙ্গ হতে পারে। প্রতারণার শিকার কর্মীর আইনি সহায়তার অধিকার আছে (ধারা ২৭)।",
            f"কাটার লিখিত কারণ চান। দূতাবাসের শ্রম কল্যাণ উইং। {HELP_ABROAD}।"),
    "R12": ("নিয়মিত বেতন না দেওয়া চুক্তিভঙ্গ। এজেন্সির গাফিলতিতে দেশে ফিরতে হলে খরচ এজেন্সিকে বহন করতে হয় (ধারা ২৯)।",
            f"দেরির তারিখগুলো লিখে রাখুন। দূতাবাসের শ্রম কল্যাণ উইং। {HELP_ABROAD}।"),
}

LEGAL_SOURCES = [
    ("The Daily Star: OEMA 2013 sections 22, 27, 28, 29, 31", "https://www.thedailystar.net/node/3391481"),
    ("The Business Standard: OEMA 2013, compensation and criminal cases", "https://www.tbsnews.net/node/260497"),
    ("The Financial Express: BMET complaint and arbitration", "https://thefinancialexpress.com.bd/views/the-migration-grievance-redress-mechanism-1547821416"),
    ("Probash Bandhu call centre 16135 and +8809610102030", "https://www.dhakatribune.com/bangladesh/293573/govt-launches-probash-bondhu-hotline-service-for"),
    ("Legal aid toll-free number 16699 (BSS)", "https://www.bssnews.net/bangla/law-and-courts/263685"),
    ("BMET-licensed agencies on the Overseas Employment Platform", "https://oep.gov.bd/"),
]


def attach(flags: list[Flag]) -> list[Flag]:
    """Add the law + next step (fixed map) and the knowledge-base passages that back them (retrieval)."""
    from . import rag
    for f in flags:
        if f.rule_id in LEGAL and not f.law_bn:
            f.law_bn, f.action_bn = LEGAL[f.rule_id]
        if not f.refs:
            try:
                f.refs = rag.refs_for_flag(f"{f.title_bn} {f.law_bn or ''}")
            except Exception:  # retrieval must never break a check
                f.refs = []
    return flags
