import contextlib
import random

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from pyrogram import Client, filters
from pyrogram.types import Message

from utils.db import db
from utils.filters import command
from utils.misc import modules_help, scheduler, scheduler_jobs
from utils.scripts import ScheduleJob, get_args_raw, get_prefix

names = [
    "*ВеСна*",
    "-=Blondex=-",
    "˙˙·٠•●Е╞╣۞т●•٠·˙˙",
    "★А мНе ВсЁ пОфИг★",
    "[♥♥♥бІлЯВ۞Чк@♥♥♥]",
    "▒▒▒彡✘a-✘a-✘a彡 ▒▒▒ ✓",
    "▿ ◀ ◁mоо↕=↕light beauty ▷►▿",
    "♪ ♪ ♪ДевYшка_8не_закон@ ♪ ♪ ♪",
    "| живу грешу... умру отвечу... |",
    "*ПрАвдА пОртИт нЕрВы*",
    "♚Теперь☛[блОнд]☚иНочк∀♚",
    "♥_I am С̶у̶п̶е̶р̶м̶э̶н_♥",
    "| нИ k@пЛи сЕрЬЁzноStи |",
    "ღChocolatE_B♥a♥b♥Yღ",
    "♔miss.pozzzitifff♔",
    "♂ ℙe®feⒸt ツ",
    "Мне по КАЙФУ",
    "..::ᵀᴴᴱ ᴼᴿᴵᴳᴵᴻᴬᴸ::..",
    "˜”*°•.Крылья◐ С۞ветов◐ Чемпи☼н.•°*”˜",
    "!!!εγωιστής!!! – эгоист",
    "◄◄◄Bl@ck D۞ g►►►",
    "\\\\\\2pizza///",
    "Superхрэн",
    "[GTA MAN]",
    "*=❤ ЧуДо 2011 ❤=*",
    "♡ʁgǝɔ оʞqvо⊥ юvɡюv♡",
    "˜”*°•۩۩сама по себе۩۩•°*”˜",
    "♥ ◊♥ИзяЩнаЯ♥◊♥",
    "~Не КиСнИ,в КоНтАкТе ЗаВиСнИ~",
    "●•٠·˙ʚ٥лнʎющɐя˙·٠•●",
    "_ДеVо4к@,kOтO®Aя )(оТеЛ@ ©4@$tьЯ",
    "|...В...ОдНОм...ЭгземПляРЕ...|",
    "˜”*°•.♥ Beyb@ ♥.•°*”˜",
    "ღღ☺ЭфФеКтНаЯ☺ღღ",
    "•.♥.•°©тЕрв(0)4k@...4k@•.♥.•°",
    "¤V смиPителЬной рубашkе¤",
    "-‘๑’-©٥ЛнЕчНаЯ-‘๑’-",
    "⎛❤♥Дежурный ангел♥❤ ⎞",
    "ღღღ©ек©уɐльнɐяღღღ",
    "♔•ЧеРтЕнОк из РаЯ•♔",
    "๏̯͡๏Тɒин©твеннɒя๏̯͡๏",
    "ツвредная малыффкаツ",
    "●●٥стр٥умная(-̮̮̃•̃)я●●",
    "▒ ♥ Зн○ЙнАя♥▒",
    "ღMi[SS]✬Kapri[ZZ]ღ",
    "◒◒◒ღƜикАрНаӃღ◒◒◒",
    "[...ПупСА...]",
    "<< ЙО}|{ИГ >>",
    "[♀+♂=♥]В♡Л♡Ю♡Б♡Л♡Е♡Н♡А[♀+♂=♥]",
    "╝╝╝╚ ╙ ангело4е|{╝╝╝╚ ╙",
    "✰✰счастливая✰✰",
    "♥ М▒А▒Л▒Ы▒Ш▒К▒А♥",
    "⎛❤♥ ˜”*°•. А√АֆТ®ØФа .•°*”˜ ♥❤ ⎞",
    "хочу ♥, отвечу взаимностью! *)",
    "ღღღ Почти♥свёл♥с♥ума.ღღღ",
    "ツ gvохɐ ʚ ɔɐdɐфɐнǝツ",
    "(•̪●)..Meλκο♡БYkO..๏̯͡๏",
    "☆˙˙· .Ha©TроениЕ -‘๑ ’- Coca✿Cola ˙˙· . ☆",
    "●•° Smell ☆ of ☆ tangerines°•●",
    "❤100pud●√ ❤ ½",
    "ღʁɐннǝʎхОღ",
    "КаТаСтРоФа №❶",
    "ღღღ Не кипиши, киса ღღღ",
    "КаРамЭлькО",
    "тВаЙА-ПоДРУжКО",
    "I{p[a]c[a]B4uI{ .!. ^^,>",
    "Хулиганочка=)>",
    "мЕго_О-цЫпа==>>",
    "АгОнИЯ в СердЦЕ>",
    "Ap( i )s( i )nKA...=)>",
    "BlOnDe_In_ChOkOlAtE",
    "[Princess Moon]",
    "***Slastёna***",
    "ღ::..Одино4ка..::ღ",
    "ОпАSнЫй ВоЗрАSт",
    "‡Призрак о†еля‡",
    "тихая зомби",
    "СамаЯ ЛюбимаЯ в АськЕ...)",
    "*220 ВоLьm",
    "_-_ЛюБлЮ_-_",
    "=+АсЬкОМанКа+=",
    "МиЛ@Я(//ДЕВА4КА//)",
    "*АниМаШkА",
    "M-@-L-i-N-k-@",
    "[.....МосЬка...]",
    "(неДур]{@",
    "Хитрий_Пупс",
    "*злюка_бобер*",
    "Самый офигенный [coca in]",
    "Подарите мне мозги",
    "[[Juicy fruit]]",
    "->Люблю жить<-",
    "SlaDkoE _ DeTKO_o",
    "*МаLыШ Бу..хD..",
    "<н@ивн@я>",
    "°•★у меня своя сказка★•",
    '"Ох*евший ребёнок"',
    "♥З̶а̶ч̶е̶р̶к̶н̶е̶м̶.̶п̶р̶о̶ш̶л̶ое♥",
    "[♥ ходячий смайлІк ♥]",
    "●•°ВКедах°•●",
    "активия с бифидабактериями",
    "ЙА_ТигрА_ЙА_рычу",
    "Рыбка с запошком",
    "[ем_ложками_счастье]",
    "-‘๑’- я не подарок - я киндер сюрприз-‘๑’-",
    "d(^.^)b + d(*_*)b",
    "~`Вдох - стоп...Задыхаюсь...`~",
    "...♥..Тіпа Тралі-Валі...",
    "..Счacтьﻉ*ﻉс'ть..",
    "[~оСтОрОжНо Я кУсАюСь~]",
    "МиНзДрАв_ПреДупРеЖд→ BloND_InKa",
    "_БеГуЩаЯ_пО_гРаБлЯм_",
    "†█Twilight█†",
    "^_^...жду трамвая!...^_^",
    "|сигаретный дым|",
    "_я тупая ЗаТо КРАСИВАЯ_",
    "(¯`'•.¸СмОтРиТе_ СтАтУс ¸.•'´¯)-",
    "лОх_пеЧальНый",
    '"Сocainovaya coca-cola"',
    "[♥*♥=♥2]",
    "(¯`'•.¸(¯`°Тсс, Я фея ´¯)¸.•'´¯)",
    "★° ПічєнькО°♡",
    "...::питаюсь радугой::..",
    "Пивная фея=))))))",
    "©©©Слепой Снайпер©©©",
    "[СтО_оБеЗьЙаНн]",
    "BezMozgOFF",
    "Утка_в_тапках",
    "((ЗеЛёНаЯ M&M'sinKa))",
    "(=маленький чертенок...=)",
    "ЗОМби_КРОШИТ_П@Ц@нов",
    "˜”*°•v٠е٠s٠♥٠н٠н٠я٠я•°*”˜",
    "♥҉♥свОбОднАЯ♥҉♥",
    ".ιllιlι І ♥ ʍυﮎι© .ιllιlι",
    "=*=ГоЛуБоГла:ЗАЯ:=*=",
    "ღ4увства♥LюБвиღ",
    "°•★ТвоЁ_©☼лнцЕ★•°",
    "Ѽ...LиLe4]{@...Ѽ",
    "ツDﻉвуш]{@_S_@Drﻉsomツ",
    "♣...[Йa]_т√ﻉ٥_S٥ Lнцﻉ...♣",
    "°*”˜˜”*°•. NаГлаYA.•°*”˜˜”*°",
    "Ƹ̴Ӂ̴ƷребёнокƸ̴Ӂ̴Ʒ",
    "★пSiх-ОdИ↕↔↕♥чКа★",
    "T_T ПоХ На ВсЁ T_T",
    "ॐbrunette chocolateॐ",
    "<<<На авке не я!!!♥",
    "°•★☆КаРеГлАзАя☆★•°",
    "♥k@prIzZn@яЯ__mIsS♥",
    "«.«.«.LoJIita.».».»",
    "♥_♥ АнИмЕшКа ♥_♥",
    "˙˙·٠•●S4@sТLиVый _ ]{оLоб4Ён]{@●•٠·˙˙",
    "♬ l ﻉ√٥ m√ lafﻉ ♬",
    "˜”*°•Сонный♚Миffка•°*”˜",
    "\"^|':Redkaja«.~.»Svolo4:'|^",
    "°*”˜˜”*°•.ПяТ@4oK•°*”˜˜”*°",
    "..:::БеЛоЕ зОлОтО:::..",
    "ҳ̸Ҳ̸ҳ Ekstrimalka ппЦ ҳ̸Ҳ̸ҳ",
    "«~*ХорошенькаЯ *~»",
    "(=___PoZzItIf___=)",
    "Ƹ̴ツХоДяЧиЙ уЛыБон:РӠ",
    "*..._ЛаПуЛя__Йа_...*",
    "°•★☆ДьяволноКРАСИВА☆★•°",
    "ᵀᴴᴱ ᴼᴿᴵᴳᴵᴻᴬᴸ",
    "Ξ[Åñ†íčhříς†]Ξ",
    "·٠•●๑۩ Bad boy ™ ۩๑●•٠·˙",
    "☺:DеТk☼☺",
    "ツ ©Ч@©Tьɐツ",
    "°°°«k@®@m€£ь»°°°",
    "▒ Ki┣┥d€® ▒",
    "*_*ViTaMiÑkA*_*",
    "-‘๑’- Т√()Я V®€ DiN@ -‘๑’-",
    "♥ХоДяЧиЙ ЗаЁб=)♥",
    "˜”*°• LЭйDI•}{oolyGanK@ •°*”˜",
    "°«_$tud€nt-|{@_»°",
    "[<~ПѐҹѐңьҜө_Ө~>]",
    "ღღღ Пуго√К@ ღღღ",
    "••• √еDьМ()ч]{@ •••",
    "(= ВЕСЕЛЫЙ ПОМИДОР =)",
    "øøø А мЫ н@ ){@╦ ){€ øøø",
    "♫♫♫ A]{- ➃➆ ♫♫♫",
    "░▒▓\/@T@R▓▒░",
    ". ·˙˙⋆♥ ҜайФøVая ♥⋆˙˙· .",
    "˜”*°•.СияНее ниБеС.•°*”˜",
    "°*”♥ღBRюнЕт@чКа в зеФиреღ♥”*°",
    "˙˙·٠♔•КоРолеВа нОЧи•♔٠·˙˙˙",
    "ღ♠ Miss★Ҝапῥиź♠ღ",
    "✬ღ●•٠·kареGлаzka·٠•●ღ✬",
    "✬˙˙°·•♀ζø√ξ ♂•·°˙˙✬",
    "˙˙°·✧Miss KatastroFFa✧·°˙˙",
    "˙˙°❤NежеnkA❤°˙˙",
    "☜♡☞ЛяЛьKa☜♡☞",
    "˙˙°❤Та SаMая❤°˙˙",
    "✬˙KISsKA˙✬",
    "˙˙°·✧Panterka✧·°˙˙",
    "*°•►►Дур{ё}ныШ◄◄•°*",
    "|̳̿В̳̿|̶к̶о̶н̶т̶а̶к̶т̶е",
    "*°••°*.♡.кYдРяШкА.♡.*°••°*",
    "♥_НеБо[_На_]ЛаДоНи_♥",
    "•♥•ღш0к0лАдღ•♥•",
    ".•°*”˜☆хУлИгАн☆˜”*°•.",
    "•♥•К♡ТьКа•♥•",
    "˜”*°•.I_HavE_[ N◌]_HearT.•°*”˜",
    "[♥ღ♥ДаВаЙ зАмУтИм СчАсТьЕ♥ღ♥]",
    "[..♥..ZabavA..♥..]",
    "•●ФуНтИк●•",
    "˜”*°•.★..Angel_Of_The_Night..★.•°*”˜",
    "☼_ஐПчЁлКаஐ_☼",
    "♬ lﻉ√٥ m√ lafﻉ ♬",
    "˜”*°•.ღNaTaLЁkღ.•°*”˜",
    "[••• пЬЯнЫй__ЁжИк •••]",
    "☜AнГeL..♡..VKeДаХ☞",
    "° chertOFFka °•",
    "*°•Все_будет_Coca-Cola•°*",
    "ღI see youღ",
    "ღБрЮнЕтОчКаღ",
    "˙˙·٠•●ONLY●•٠·˙˙",
    "♔Madе_in_РАЙ♔",
    "ıIıIİıİIıımusic",
    "[...★ХрУмиК★...]",
    "ОрбИт_бЕЗ_сАхАрА",
    "*БеЛыЙ ЗаЙ*",
    "★ Sияние_zвездЫ ★",
    "***Slastёna***",
    "♠♥ВзгЛяд в НикУдА♥♠",
    "ジfunny_chelove©hik ジ",
    "хру©талЬная_©леzа",
    "©упер-пупеp_девасЬka",
    "♥~ romantic_girl ~♥",
    "”*°•.dreamy_girl.•°*”",
    "♥ your_dream ♥",
    "♕Ко®олева♕",
    "ツ_улыбни©ь_ツ",
    "˜”*°•.БлеSSSтяШк@ .•°*”˜",
    "$ ТОНУ В МАR|TINI $",
    "«®еSpЕkt МНЕ и ув@)|(уХ@»",
    "Х()4еШЬ БыТЬ на М()ЁМ УР()VNЕ --> STА®@ЙSЯ",
    ")/(о/\таЯ пх|/|хАААпаТТТка",
    "⎷⎛)̅ζø√ξ⎷⎛",
    "♥МеЧтЫ_СбУдУтСЯ♥",
    "✖МаLяtКо✖",
    "٠•●๑ ⎝⏠⏝⏠⎠ ๑●•٠·",
    "♔♒☠샖 (•̪●)샖 ☠♒♅♔",
    "ღששRadugaששღ",
    "˙·٠●◇ГолубоглаЗАЯ◇●٠·˙",
    "° •★Счастье_снова_в_модЕ★•",
    "ღ⎠⎛ღ√ Ne@DeK√@Te ღ⎞⎝ღ",
    "√√√◀ NЕжNыЙ яД ▶√√√",
    "(¯`'•.¸•NE♥AnGeL•¸.•'´¯)̶",
    "♡♡♡because of you♡♡♡",
    "••• ツツ4ум()в()й Дiн()З@ВрiК ツツ•••",
    "˙˙·٠•● ☆Доступ к [ღ] закрыт ☆●•٠",
    "●•°••Шоколадная_фАнТаЗиЯ●•°••",
    "~~°°°СеРдЦе БьЕтСя°°°~~",
    "в©Ё К▢гda ┭▢ К▢╠▬╣4ае┲©я",
    "❤● • [В НеАдЕкВаТе ] • ●❤",
    "*... а глазки то блестят у...*",
    "¥$< Made_iN_мАм@>$¥",
    "♀♀♀ R@$$лаБь©Я дЕ┭▢4k@ ♀♀♀",
    "'•¸•▪♥ МеЖдУ нАмИ рАй♥▪•¸•'´¯",
    "*°•M@LENьI{ИЙ 4Е{LOVE}4игГг•°*",
    "·٠•●๑۩ I{иNDЕR $URpRиzZz۩๑●•٠·˙",
    "●•°• }I{иVy [mЕ]4ТoЙ●•°•",
    'Ѽ"X[o]4y LeT[o]"Ѽ',
    '(¯"°*” ˜О$I{OLo4eгГг $4@$TьЯ˜”*°"¯)',
    ".•°*” ˜Ѽ♥$oOoLNЫ$I{o-Я ♥Ѽ ˜”*°•.",
    "✬••٠·♥[в] O}I{иD@НиИ 4уD@♥••٠·✬",
    "ҳ̸Ҳ̸ҳ М@НЬ[ЙА]I{ $ [NеI{O] УIIII{@MИ ҳ̸Ҳ̸ҳ",
    '••٠·♥"[ Б@НЬТИ{]"♥••٠·',
    ".•°*” ˜►☜♡☞[... $ТУDEНТI{@...]☜♡☞◄ ˜”*°•.",
    "(¯.•°*” ⎷⎛МЫIIIЬ ⎷⎛ ˜”*°•.¯)",
    "♥♥♥[Ска}|{и] [Ты] [МенЯ] [ЛюбиШь] [?]♥♥♥",
    "••٠·♥[Т◍Льк◍ Тв◍Я]♥••٠·",
    "˜”*°•.ToL'Ko TvoYa.•°*”˜",
    "♥♥♥Только_٩(-̮̮̃-̃)۶_Тво[Я]♥♥♥",
    "●•°••`ШтуЧка_к_кøТорøЙ♥тЯнуТся_рУчКи`●•°••",
    "๑۩۩๑✬ T@[NЮIII@]✬๑۩۩๑",
    "(¯`'•¸•▪♥ M@RгОIII@♥▪•¸•'´¯)",
    "·٠•● MЭRI ●•٠·",
    "(¯`'•¸•▪♥[ М@RИНI{@]♥▪•¸•'´¯)",
    ".•°*”˜ღ... [Н@$Т]ЮIII@-[Я]...ღ˜”*°•",
    "{СоJIнТсЕ}",
    "~$тЕрВ¤Чк@~",
    "]{р@$опеТо4){@",
    "Без_]{omпле]{$oB",
    "[...::XyLiGAn4iK::..]",
    "♥(ٿ)HoT gIrL(ٿ)♥",
    "♥BARBIE♥",
    "ღDollღ",
    "ПриНЦеФФФко",
    "$((ЛапОчкА))$",
    "°• БуСИНкА •°",
    "| [~Cold♥heart~]TM|",
    "[Ǝɦнv☼Ɔ]",
    "~*{BoLshe_ne_KoLю4K@}*~",
    "*ТуЦ_٩(̾●̮̮̃̾•̃̾)۶_ТуЦ БЭйБи*",
    "Made in МаМа",
    "♥♥♥a )-( г е /\ () ч е |(♥♥♥",
    "...♥BloNdiNk@♥...",
    "°•..KittY..•°",
    "★.•*ГолУбоГлаЗа Я*•.★",
    ".•°*”˜AnGeLyTkO˜”*°•.",
    "*** К@пRизЮ/\ьk@ ***",
    "^^ПyП$икИ РуЛяТ^^",
    "♣تЧеРтЕнОk из РаЯت♣",
    "ŚάΜΑЯ ѕ4à©ŤλиВάЯ!",
    "*RE$PECT*",
    "★з♥а♦я♣ц★™",
    "♡˜”°•П☈☉кλяTаЯ р@Ем•°”˜♡",
    "♥˜”*°•ΔыΨу ТоБоЙ •°*”˜ ♥",
    "♥˜”*°•П☈☉сTи ̴Ʒа βсЁ•°*”˜ ♥",
    "๑۩۩๑๑λюБи МеNя๑۩۩๑๑",
    "✿٠★П☈☉сT☉ ƷΔ☉хλа ★٠✿",
    "(¯`'•.¸ИгNo☈щиц@¸.•'´¯)",
    "..:::λучшаЯ СказкА:::..",
    "(¯`'•.¸βерНусь в ПроШλ☉е¸.•'´¯)",
    "..:::РяΔ☉М с t☉Бой:::..",
    "★ღ°•Я РяΔ☉М•°ღ★",
    "ஐღ⎠⎛ღToLьko TvоЯღ⎞⎝ღஐ",
    "[♡ тβой N@R]{оти]{ ♡]",
    "˜ ° ღ~NаивNаЯ и Δ☉бRaя~ღ ° ˜",
    "˜ ° ღ~П٥ЧтИ ЧуΔ٥.~ღ ° ˜",
    "`'•.¸✿Пр٥щать - сv٥йств٥ сильNог٥.✿¸.•'´",
    "•̪●NﻉРﻉшительн☉сть - vор v☉зможNости.•̪●",
    "ღ\\\\\\лОvи св☉й ДеNь.///ღ",
    "ღღღЛюб☉vь нﻉ ищﻉт совﻉршﻉнстv.ღღღ",
    "=Парад☉ксы - лишь прикрытие.=",
    "ۘەۥۤۡۢ۠۰ۭۛۘۖ٠ٍ٫ء٠Люб☉βь β☉прﻉки.ۘەۥۤۡۢ۠۰ۭۛۘۖ٠ٍ٫ء٠",
    "♥˙˙·٠•●Благ☉ β чувствﻉ мере.●•٠·˙˙♥",
    "˜”*°•.♥β поискﻉ дNа печали♥.•°*”˜.",
    "·٠•●๑...Дар любβи - потакаNиﻉ....๑●•٠·˙",
    "°•★У любβи нﻉт глаз.★•°",
    "ѼУмирать ☉т любβи - жить ﻉю.Ѽ",
    "ஐღ⎠⎛ღмÅрИш☉н]{а-]{❍րNиш☉н]{аღ⎞⎝ღஐ",
    "♡˜”°•ІրискÅ•°”˜♡",
    "๑۩۩๑๑ІRиСк@๑۩۩๑๑",
    "ஐღ⎠ІRиc]{а⎝ღஐ",
    "๑۩БоГиНя۩Ů",
    "❀〷√ﻉRNись〷❀",
    "ღღღАнГﻉλ❍чﻉКღღღ",
    "˜ ° ღ~@нГﻉﻉλ❍ЧеК~ღ ° ˜",
    "·٠•●๑...АNгﻉλ☉ЧеК....๑●•٠·˙",
    "ღ·٠•●๑...ღАнГﻉλ❍чﻉ]{ღ....๑●•٠·˙ღ",
    "(¯`ИнҖӘнӘR´¯)",
    "̴Ӂ̴Ʒ ШṰץҸ]{@ Ƹ̴Ӂ̴",
    "♥۲лΫΠἕњ]{@ Я♥",
    "☼бМἕΝЯл@ ]{ṔылเЯ Ν@ л♥б☼βเ",
    "Ƹ̴Ӂ̴Ʒ Ё]/[ИҸẾГ Ƹ̴Ӂ̴Ʒ",
    "[♥ЂÀмЂҰҸã♥]",
    "Ƹ̴Ӂ̴Ʒ ПёҸѐŉь]{@ Ƹ̴Ӂ̴Ʒ",
    "♥$ҰљΤ®@ΦиỖлĔΤ$♥",
    "☜ kN◎P○4k@ ☞",
    "╳ P@®人@mEn┳╳",
    "✿AkT®iS@✿",
    "☆k®aSi√@яЯ kAk zZ✔eZd@☆",
    "...:::Йа |{♕®♔le√@:::...",
    "ﻩ*ﻩ*ﻩСнЕжИнКа_Из_КаПлИ_дОжДяﻩ*ﻩ*ﻩ",
    "☀ПуФыСтЫй ЗаЙкА☀",
    "⎞★f@ntA★⎛",
    "۞__@nImE__۞",
    "♥˙˙·٠•●Чудо в Кедах●•٠·˙˙♥",
    "ツМаLinK@ツ",
    "⎛⎝kO_otЯя®a__cR@zZY⎠⎞",
    "☆чЕ®Nik@☆",
    "***СнеƸ̴Ӂ̴Ʒинка***",
    "☜bEyB◉4k@☞",
    "♥˙˙·٠•●Ангел в Кедах●•٠·˙˙♥",
    "✿Сl@dKaяЯ✿",
    "๑۩__ц@rsk@яЯ__ZzAbA√@__۩๑",
    "ツпР◉s╥◉__уmNiчkO_o ツ",
    "✿__✔eRo_OniK@__ ✿",
    "⎛⎝ღ °•★ маленьkое_чудо ★•° ღ⎛⎝",
    "♥Я люблю ̶т̶е̶б̶я̶ ...СЕБЯ♥",
    "(¯`'•.¸•°▪♥НежнаЯ♥▪°•¸.•'´¯)",
    "☜♡☞★ღツЛюБлЮツღ★☜♡☞",
    "̷А̷н̷Г̷е̷Л̷ ̷Б̷е̷З̷ ̷Д̷у̷Ш̷и̷ ̷И̷ ̷т̷Е̷л̷А",
    "ÅЛℯKℭÅℋД®θℬℋÅ",
    ":)BloNdiNk@:)",
    "~~~$DRAкON$~~~",
    "❶Swe[e]T*dreaM❶",
    "˙˙·٠•●☆МалЕньКаЯ__бусИчкА☆●•٠",
    "*☆KoPoLeVa☆*",
    "˙·٠•●๑...ЛучиК__СолнцА...๑●•٠·˙",
    "ЧуПа٩(̾●̮̮̃̾•̃̾)۶ЧуПсА",
    "☭ СССР ☭",
    "˙·٠-●๑..Ray__of a Sun..๑●-٠·˙",
    "(̅_̅_̅_̅(̅̅̅̅̅̅(̅_̅_̅_̅K̅E̅N̅T̅_̅_̅_̅̅_̅_̅_̅()",
    "⎞⎞⎞⎠♥♥♥БОБРИШКА♥♥♥⎠⎞⎞⎞",
    "_$_ .KRO$HK@._$_",
    "(_ $_ .K€NT._ $_ )",
    "(.^_^. K¡tt¡`k€t .^_^.)",
    "$SImPoTяЖк@$",
    "★☆ВечНо_ПьянЫй☆★",
    "ღღღ₵√℮Ⱡⱥღღღ",
    "(.¥.TH€.¥OU.LOV€.)",
    "●•╚╣Ύ╔╗å╚╣Ύ╔╗ℂ●•",
    "(.$.>>>.JU¡C¥.<<<.$.)",
    "(¯`'•.¸(¯Зαй|{α´¯)¸.•'´¯)",
    "˜ ° ღ~БРюНﻉТ]{А~ღ ° ˜",
    "♥_*l ٥ ﻻ_ ﻉ √ ٥ υ*_♥",
]


@Client.on_message(~filters.scheduled & command(["icq"]) & filters.me & ~filters.forwarded)
async def nickname_handler(client: Client, message: Message):
    args = get_args_raw(message)
    if not args:
        return await message.edit_text(
            "<emoji id=5260342697075416641>❌</emoji><b> State didn't provided</b>",
            quote=True,
        )
    if args.lower() not in ("on", "off", "1", "0", "true", "false"):
        return await message.edit_text(
            "<emoji id=5260342697075416641>❌</emoji><b> State should be True or False</b>",
            quote=True,
        )

    me = await client.get_me()
    if args.lower() in ("on", "1", "true"):
        if db.get("icq_names", "enabled"):
            return await message.edit_text(
                "<emoji id=5260342697075416641>❌</emoji><b> ICQ Names already enabled</b>"
            )

        db.set("icq_names", "enabled", True)
        first_name = me.first_name
        last_name = "" if me.last_name is None else me.last_name
        db.set("icq_names", "original_name", {"first_name": first_name, "last_name": last_name})
        try:
            await client.update_profile(first_name=random.choice(names), last_name="")
        except Exception as e:
            return await message.edit_text(
                f"<emoji id=5260342697075416641>❌</emoji><b>Cant change name for now\n\nError{e}</b>"
            )
    else:
        db.set("icq_names", "enabled", False)
        original_name = db.get("icq_names", "original_name")
        try:
            await client.update_profile(
                first_name=original_name["first_name"], last_name=original_name["last_name"]
            )
        except Exception as e:
            return await message.edit_text(
                f"<emoji id=5260342697075416641>❌</emoji><b>Cant change name for now\n\nError{e}</b>"
            )

    await message.edit_text(
        f"<emoji id=5260726538302660868>✅</emoji><b> ICQ Names state succesfuly set to {args}</b>"
    )


@Client.on_message(~filters.scheduled & command(["icqr"]) & filters.me & ~filters.forwarded)
async def nickname_random_handler(client: Client, message: Message):
    if not db.get("icq_names", "enabled", False):
        return await message.edit_text(
            "<emoji id=5260342697075416641>❌</emoji><b> ICQ Names should be enabled</b>"
        )

    try:
        await client.update_profile(first_name=random.choice(names), last_name="")
    except Exception as e:
        return await message.edit_text(
            f"<emoji id=5260342697075416641>❌</emoji><b>Cant change name for now\n\nError{e}</b>"
        )


@Client.on_message(~filters.scheduled & command(["icqt"]) & filters.me & ~filters.forwarded)
async def nickname_trigger_handler(_: Client, message: Message):
    args = get_args_raw(message)

    # job_id is always job function name
    job = scheduler.get_job(icq_names_job.__name__)

    if not args:
        if isinstance(job.trigger, CronTrigger):
            fields = ["minute", "hour", "day", "month", "day_of_week"]
            values = {
                field.name: str(field) for field in job.trigger.fields if field.name in fields
            }
            cron_expression = [values[field] for field in fields]
            text = (
                "<b>Current trigger is Cron.\n"
                f"Next run time: {job.next_run_time}\n"
                f"Current cron expression:</b> <code>{' '.join(cron_expression)}</code>"
            )
        if isinstance(job.trigger, IntervalTrigger):
            text = (
                "<b>Current trigger is Interval.\n"
                f"Next run time: {job.next_run_time}\n"
                f"Current interval: {job.trigger.interval}</b>"
            )
        return await message.edit_text(
            f"{text}\n\n<b>For change trigger use</b> <code>{get_prefix()}icqt [cron/interval] [values]</code>"
        )

    if len(args.split()) < 2:
        return await message.edit_text(
            "<emoji id=5260342697075416641>❌</emoji><b> Trigger type and values didn't provided</b>"
        )

    if args.split()[0].lower() not in ("cron", "interval"):
        return await message.edit_text(
            "<emoji id=5260342697075416641>❌</emoji><b> Trigger type should be Cron or Interval</b>"
        )

    # Values should be like this for cron:
    # 0 4 8-14 * * (at 04:00 on every day-of-month from 8 through 14)
    if args.split()[0].lower() == "cron":
        try:
            trigger = CronTrigger.from_crontab(args.split(maxsplit=1)[1])
            job.reschedule(trigger=trigger)
            db.set(
                "triggers",
                icq_names_job.__name__,
                {"type": "cron", "value": args.split(maxsplit=1)[1]},
            )
        except ValueError:
            return await message.edit_text(
                "<emoji id=5260342697075416641>❌</emoji><b> Invalid cron expression</b>"
            )
    # Or like this for interval:
    # 3600 (IN SECONDS)
    else:
        try:
            trigger = IntervalTrigger(seconds=int(args.split(maxsplit=1)[1]))
            job.reschedule(trigger=trigger)
            db.set(
                "triggers",
                icq_names_job.__name__,
                {"type": "interval", "value": int(args.split(maxsplit=1)[1])},
            )
        except ValueError:
            return await message.edit_text(
                "<emoji id=5260342697075416641>❌</emoji><b> Invalid interval</b>"
            )

    await message.edit_text(
        "<emoji id=5260726538302660868>✅</emoji><b> Trigger succesfuly changed</b>"
    )


# First argument always should be client. Because it will be passed automatically in main.py
async def icq_names_job(client: Client):
    if not db.get("icq_names", "enabled", False):
        return

    with contextlib.suppress(Exception):
        await client.update_profile(first_name=random.choice(names), last_name="")


scheduler_jobs.append(ScheduleJob(icq_names_job))

modules_help["icq"] = {
    "icq [on/off]": "Turn on/off icq names",
    "icqt": "Set trigger for icq names",
    "icqr": "Change name to random one immediately",
}
