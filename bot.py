
import os, sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN", "")
DB = os.getenv("DATABASE", "ativa_pix.db")
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}

def now():
    return datetime.utcnow().isoformat(timespec="seconds")

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      telegram_id INTEGER UNIQUE NOT NULL,
      username TEXT, name TEXT,
      balance REAL DEFAULT 0,
      total_received REAL DEFAULT 0,
      total_withdrawn REAL DEFAULT 0,
      referred_by INTEGER,
      blocked INTEGER DEFAULT 0,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS campaigns(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      reward REAL NOT NULL,
      target INTEGER NOT NULL,
      status TEXT DEFAULT 'active',
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS activations(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      campaign_id INTEGER NOT NULL,
      status TEXT DEFAULT 'pending',
      proof_file_id TEXT,
      proof_type TEXT,
      created_at TEXT NOT NULL,
      reviewed_at TEXT
    );
    CREATE TABLE IF NOT EXISTS withdrawals(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL,
      amount REAL NOT NULL,
      pix_key TEXT NOT NULL,
      status TEXT DEFAULT 'pending',
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS referrals(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      inviter_id INTEGER NOT NULL,
      invited_id INTEGER UNIQUE NOT NULL,
      status TEXT DEFAULT 'pending',
      reward REAL DEFAULT 0,
      created_at TEXT NOT NULL
    );
    """)
    if not c.execute("SELECT 1 FROM campaigns WHERE status='active'").fetchone():
        c.execute(
            "INSERT INTO users(telegram_id,username,name,created_at) VALUES(?,?,?,?)",
    c.commit()
    c.close()

def get_user(tg):
    c = db()
    u = c.execute("SELECT * FROM users WHERE telegram_id=?", (tg.id,)).fetchone()
    if not u:
        c.execute(
            "INSERT INTO users(telegram_id,username,name,created_at) VALUES(?,?,?,?,?)",
            (tg.id, tg.username, tg.full_name, now())
        )
        c.commit()
        u = c.execute("SELECT * FROM users WHERE telegram_id=?", (tg.id,)).fetchone()
    c.close()
    return u

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 PARTICIPAR", callback_data="campaign"),
         InlineKeyboardButton("💰 MEU SALDO", callback_data="balance")],
        [InlineKeyboardButton("👥 INDICAR AMIGOS", callback_data="ref"),
         InlineKeyboardButton("📊 ATIVAÇÕES", callback_data="acts")],
        [InlineKeyboardButton("💸 SACAR", callback_data="withdraw"),
         InlineKeyboardButton("📜 REGRAS", callback_data="rules")],
        [InlineKeyboardButton("🛠️ ADMIN", callback_data="admin")]
    ])

def back():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ MENU", callback_data="menu")]])

async def start(update, context):
    u = get_user(update.effective_user)

    if context.args:
        try:
            inviter_tid = int(context.args[0])
            if inviter_tid != u["telegram_id"]:
                c = db()
                inviter = c.execute(
                    "SELECT id FROM users WHERE telegram_id=?", (inviter_tid,)
                ).fetchone()
                exists = c.execute(
                    "SELECT 1 FROM referrals WHERE invited_id=?", (u["id"],)
                ).fetchone()
                if inviter and not exists:
                    c.execute(
                        "INSERT INTO referrals(inviter_id,invited_id,created_at) VALUES(?,?,?)",
                        (inviter["id"], u["id"], now())
                    )
                    c.execute(
                        "UPDATE users SET referred_by=? WHERE id=?",
                        (inviter["id"], u["id"])
                    )
                    c.commit()
                c.close()
        except ValueError:
            pass

    await update.message.reply_text(
        f"🤖 *ATIVA PIX BOT*\n\n"
        f"Olá, {u['name']}! 👋\n\n"
        f"💰 Saldo: R$ {u['balance']:.2f}\n"
        f"Escolha uma opção:",
        parse_mode="Markdown",
        reply_markup=menu()
    )

async def callbacks(update, context):
    q = update.callback_query
    await q.answer()
    u = get_user(q.from_user)

    if q.data == "menu":
        await q.edit_message_text(
            f"🤖 *ATIVA PIX BOT*\n\n💰 Saldo: R$ {u['balance']:.2f}\n\nEscolha uma opção:",
            parse_mode="Markdown", reply_markup=menu()
        )

    elif q.data == "campaign":
        c = db()
        camp = c.execute(
            "SELECT * FROM campaigns WHERE status='active' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not camp:
            c.close()
            await q.edit_message_text("🚫 Nenhuma campanha ativa.", reply_markup=back())
            return
        n = c.execute(
            "SELECT COUNT(*) n FROM activations WHERE user_id=? AND campaign_id=? AND status='approved'",
            (u["id"], camp["id"])
        ).fetchone()["n"]
        c.close()

        await q.edit_message_text(
            f"🚀 *{camp['name']}*\n\n"
            f"🎯 Meta: {camp['target']} ativações\n"
            f"💰 Recompensa: R$ {camp['reward']:.2f}\n"
            f"📊 Progresso: {n}/{camp['target']}\n\n"
            "Realize a ação descrita pela campanha e envie o comprovante para análise.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📨 ENVIAR COMPROVANTE", callback_data="proof")],
                [InlineKeyboardButton("⬅️ MENU", callback_data="menu")]
            ])
        )

    elif q.data == "proof":
        context.user_data["awaiting_proof"] = True
        await q.edit_message_text(
            "📨 Envie agora uma FOTO ou DOCUMENTO do comprovante.\n\n"
            "Não envie senhas, códigos SMS ou credenciais bancárias."
        )

    elif q.data == "balance":
        await q.edit_message_text(
            f"💰 *MEU SALDO*\n\n"
            f"Disponível: R$ {u['balance']:.2f}\n"
            f"Total recebido: R$ {u['total_received']:.2f}\n"
            f"Total sacado: R$ {u['total_withdrawn']:.2f}",
            parse_mode="Markdown", reply_markup=back()
        )

    elif q.data == "acts":
        c = db()
        rows = c.execute(
            """SELECT a.status, ca.name FROM activations a
               JOIN campaigns ca ON ca.id=a.campaign_id
               WHERE a.user_id=? ORDER BY a.id DESC LIMIT 10""",
            (u["id"],)
        ).fetchall()
        c.close()
        txt = "📊 *ATIVAÇÕES*\n\n"
        txt += "\n".join(
            f"• {r['name']}: {r['status']}" for r in rows
        ) if rows else "Nenhuma ativação registrada."
        await q.edit_message_text(txt, parse_mode="Markdown", reply_markup=back())

    elif q.data == "ref":
        bot = await context.bot.get_me()
        link = f"https://t.me/{bot.username}?start={u['telegram_id']}"
        c = db()
        n = c.execute(
            "SELECT COUNT(*) n FROM referrals WHERE inviter_id=?", (u["id"],)
        ).fetchone()["n"]
        c.close()
        await q.edit_message_text(
            f"👥 *INDICAÇÕES*\n\n"
            f"Seu link:\n`{link}`\n\n"
            f"👥 Indicados: {n}\n\n"
            "Recompensas de indicação dependem dos critérios definidos na campanha.",
            parse_mode="Markdown", reply_markup=back()
        )

    elif q.data == "withdraw":
        if u["balance"] < 5:
            await q.edit_message_text(
                "💸 O saldo mínimo para solicitar saque é R$ 5,00.",
                reply_markup=back()
            )
        else:
            context.user_data["awaiting_pix"] = True
            await q.edit_message_text(
                f"💸 Saldo disponível: R$ {u['balance']:.2f}\n\n"
                "Envie sua chave Pix. O pedido ficará pendente para análise administrativa."
            )

    elif q.data == "rules":
        await q.edit_message_text(
            "📜 *REGRAS*\n\n"
            "• Leia as condições de cada campanha.\n"
            "• Ativações precisam ser verificáveis.\n"
            "• Comprovantes podem ser revisados.\n"
            "• Contas duplicadas ou fraude podem ser bloqueadas.\n"
            "• Saques ficam sujeitos à análise.\n"
            "• Nunca envie senha, token ou código SMS bancário.",
            parse_mode="Markdown", reply_markup=back()
        )

    elif q.data == "admin":
        if q.from_user.id not in ADMIN_IDS:
            await q.answer("Acesso restrito.", show_alert=True)
            return
        await admin_panel(q)

    elif q.data.startswith("approve:") or q.data.startswith("reject:"):
        if q.from_user.id not in ADMIN_IDS:
            return
        await review_activation(q, context)

    elif q.data.startswith("wd_"):
        if q.from_user.id not in ADMIN_IDS:
            return
        await review_withdrawal(q, context)

async def admin_panel(q):
    c = db()
    users = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
    pending = c.execute(
        "SELECT COUNT(*) n FROM activations WHERE status='pending'"
    ).fetchone()["n"]
    withdrawals = c.execute(
        "SELECT COUNT(*) n FROM withdrawals WHERE status='pending'"
    ).fetchone()["n"]
    c.close()
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 ESTATÍSTICAS", callback_data="astats")],
        [InlineKeyboardButton("⚡ ATIVAÇÕES PENDENTES", callback_data="apending")],
        [InlineKeyboardButton("💸 SAQUES PENDENTES", callback_data="wpending")],
        [InlineKeyboardButton("⬅️ MENU", callback_data="menu")]
    ])
    await q.edit_message_text(
        f"🛠️ *PAINEL ADMIN*\n\n👥 Usuários: {users}\n"
        f"⚡ Ativações pendentes: {pending}\n💸 Saques pendentes: {withdrawals}",
        parse_mode="Markdown", reply_markup=kb
    )

async def review_activation(q, context):
    action, aid = q.data.split(":")
    aid = int(aid)
    c = db()
    a = c.execute("SELECT * FROM activations WHERE id=?", (aid,)).fetchone()
    if not a or a["status"] != "pending":
        c.close()
        await q.answer("Esta ativação já foi processada.", show_alert=True)
        return

    if action == "approve":
        c.execute(
            "UPDATE activations SET status='approved', reviewed_at=? WHERE id=?",
            (now(), aid)
        )
        user_id = a["user_id"]
        camp = c.execute(
            "SELECT * FROM campaigns WHERE id=?", (a["campaign_id"],)
        ).fetchone()
        approved = c.execute(
            "SELECT COUNT(*) n FROM activations WHERE user_id=? AND campaign_id=? AND status='approved'",
            (user_id, a["campaign_id"])
        ).fetchone()["n"]

        # Reward once when target is reached.
        if approved >= camp["target"]:
            already = c.execute(
                """SELECT 1 FROM activations WHERE user_id=? AND campaign_id=?
                   AND status='rewarded'""",
                (user_id, a["campaign_id"])
            ).fetchone()
            if not already:
                c.execute(
                    """UPDATE users SET balance=balance+?, total_received=total_received+?
                       WHERE id=?""",
                    (camp["reward"], camp["reward"], user_id)
                )
                c.execute(
                    """UPDATE activations SET status='rewarded'
                       WHERE user_id=? AND campaign_id=? AND status='approved'""",
                    (user_id, a["campaign_id"])
                )
                notify = c.execute(
                    "SELECT telegram_id FROM users WHERE id=?", (user_id,)
                ).fetchone()
                c.commit()
                c.close()
                try:
                    await context.bot.send_message(
                        notify["telegram_id"],
                        f"🎉 Campanha concluída!\n\n💰 R$ {camp['reward']:.2f} foi adicionado ao seu saldo."
                    )
                except Exception:
                    pass
                await q.edit_message_caption("✅ Ativação aprovada e recompensa liberada.")
                return
    else:
        c.execute(
            "UPDATE activations SET status='rejected', reviewed_at=? WHERE id=?",
            (now(), aid)
        )
    c.commit()
    c.close()
    await q.edit_message_caption("✅ Processado.")

async def review_withdrawal(q, context):
    action, wid = q.data.split(":")
    wid = int(wid)
    c = db()
    w = c.execute("SELECT * FROM withdrawals WHERE id=?", (wid,)).fetchone()
    if not w or w["status"] != "pending":
        c.close()
        await q.answer("Saque já processado.", show_alert=True)
        return

    u = c.execute("SELECT * FROM users WHERE id=?", (w["user_id"],)).fetchone()
    if action == "wd_approve":
        if u["balance"] < w["amount"]:
            c.execute("UPDATE withdrawals SET status='rejected' WHERE id=?", (wid,))
            status = "rejected"
        else:
            c.execute(
                "UPDATE users SET balance=balance-?, total_withdrawn=total_withdrawn+? WHERE id=?",
                (w["amount"], w["amount"], u["id"])
            )
            c.execute("UPDATE withdrawals SET status='approved' WHERE id=?", (wid,))
            status = "approved"
    else:
        c.execute("UPDATE withdrawals SET status='rejected' WHERE id=?", (wid,))
        status = "rejected"
    c.commit()
    c.close()
    try:
        await context.bot.send_message(
            u["telegram_id"],
            f"💸 Solicitação de saque #{wid}: {status}."
        )
    except Exception:
        pass
    await q.edit_message_text(f"💸 Saque #{wid}: {status}.")

async def incoming(update, context):
    u = get_user(update.effective_user)

    if context.user_data.get("awaiting_pix") and update.message.text:
        key = update.message.text.strip()
        if len(key) < 3:
            await update.message.reply_text("Chave Pix inválida. Envie novamente.")
            return

        c = db()
        c.execute(
            "INSERT INTO withdrawals(user_id,amount,pix_key,status,created_at) VALUES(?,?,?,?,?)",
            (u["id"], u["balance"], key, "pending", now())
        )
        wid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.commit()
        c.close()

        context.user_data.pop("awaiting_pix", None)
        await update.message.reply_text(
            f"✅ Solicitação #{wid} registrada.\n"
            f"Valor: R$ {u['balance']:.2f}\nStatus: pendente.",
            reply_markup=menu()
        )

        for admin in ADMIN_IDS:
            try:
                kb = InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ APROVAR", callback_data=f"wd_approve:{wid}"),
                    InlineKeyboardButton("❌ REJEITAR", callback_data=f"wd_reject:{wid}")
                ]])
                await context.bot.send_message(
                    admin,
                    f"💸 NOVO SAQUE #{wid}\n"
                    f"Usuário: {u['name']} (@{u['username'] or '-'})\n"
                    f"Valor: R$ {u['balance']:.2f}\n"
                    f"Chave Pix: {key}",
                    reply_markup=kb
                )
            except Exception:
                pass
        return

    if context.user_data.get("awaiting_proof") and (update.message.photo or update.message.document):
        c = db()
        camp = c.execute(
            "SELECT * FROM campaigns WHERE status='active' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not camp:
            c.close()
            await update.message.reply_text("Nenhuma campanha ativa.")
            return

        fid = update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id
        typ = "photo" if update.message.photo else "document"
        c.execute(
            """INSERT INTO activations(user_id,campaign_id,status,proof_file_id,proof_type,created_at)
               VALUES(?,?,?,?,?,?)""",
            (u["id"], camp["id"], "pending", fid, typ, now())
        )
        aid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.commit()
        c.close()

        context.user_data.pop("awaiting_proof", None)
        await update.message.reply_text(
            f"📨 Comprovante recebido.\nAtivação #{aid} está pendente de análise.",
            reply_markup=menu()
        )

        for admin in ADMIN_IDS:
            try:
                kb = InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ APROVAR", callback_data=f"approve:{aid}"),
                    InlineKeyboardButton("❌ REJEITAR", callback_data=f"reject:{aid}")
                ]])
                caption = f"Ativação #{aid} | {u['name']}"
                if typ == "photo":
                    await context.bot.send_photo(admin, fid, caption=caption, reply_markup=kb)
                else:
                    await context.bot.send_document(admin, fid, caption=caption, reply_markup=kb)
            except Exception:
                pass
        return

    await update.message.reply_text("Use /start para abrir o menu.", reply_markup=menu())

async def admin_command(update, context):
    if update.effective_user.id not in ADMIN_IDS:
        return
    c = db()
    users = c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
    acts = c.execute("SELECT COUNT(*) n FROM activations WHERE status='pending'").fetchone()["n"]
    wds = c.execute("SELECT COUNT(*) n FROM withdrawals WHERE status='pending'").fetchone()["n"]
    c.close()
    await update.message.reply_text(
        f"🛠️ ADMIN\n\n👥 Usuários: {users}\n⚡ Ativações pendentes: {acts}\n💸 Saques pendentes: {wds}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🛠️ ABRIR PAINEL", callback_data="admin")]])
    )

async def admin_extra(update, context):
    q=update.callback_query
    if q.from_user.id not in ADMIN_IDS:
        return
    await q.answer()
    if q.data=="astats":
        c=db()
        total=c.execute("SELECT COUNT(*) n FROM users").fetchone()["n"]
        approved=c.execute("SELECT COUNT(*) n FROM activations WHERE status IN ('approved','rewarded')").fetchone()["n"]
        pending=c.execute("SELECT COUNT(*) n FROM activations WHERE status='pending'").fetchone()["n"]
        c.close()
        await q.edit_message_text(f"📊 ESTATÍSTICAS\n\n👥 Usuários: {total}\n⚡ Aprovadas: {approved}\n🟡 Pendentes: {pending}",reply_markup=back())
    elif q.data=="apending":
        c=db(); rows=c.execute("""SELECT a.id,u.name,ca.name campaign FROM activations a
            JOIN users u ON u.id=a.user_id JOIN campaigns ca ON ca.id=a.campaign_id
            WHERE a.status='pending' ORDER BY a.id DESC LIMIT 20""").fetchall(); c.close()
        txt="⚡ ATIVAÇÕES PENDENTES\n\n"+("\n".join(f"#{r['id']} • {r['name']} • {r['campaign']}" for r in rows) if rows else "Nenhuma.")
        await q.edit_message_text(txt,reply_markup=back())
    elif q.data=="wpending":
        c=db(); rows=c.execute("""SELECT w.id,u.name,w.amount,w.pix_key FROM withdrawals w
            JOIN users u ON u.id=w.user_id WHERE w.status='pending' ORDER BY w.id DESC LIMIT 20""").fetchall(); c.close()
        txt="💸 SAQUES PENDENTES\n\n"+("\n".join(f"#{r['id']} • {r['name']} • R$ {r['amount']:.2f}\nPix: {r['pix_key']}" for r in rows) if rows else "Nenhum.")
        await q.edit_message_text(txt,reply_markup=back())

def main():
    if not TOKEN:
        raise SystemExit("Defina BOT_TOKEN antes de iniciar.")
    init_db()
    app=Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("admin",admin_command))
    app.add_handler(CallbackQueryHandler(admin_extra,pattern="^(astats|apending|wpending)$"))
    app.add_handler(CallbackQueryHandler(callbacks))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, incoming))
    print("Ativa Pix Bot iniciado.")
    app.run_polling()

if __name__=="__main__":
    main()
