-- Market-Neutral Hedge Builder: Supabase Initial Schema & RLS Policies
-- Stage 2: Hosted Multi-User Authentication and Accounting

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Profiles Table
CREATE TABLE IF NOT EXISTS public.profiles (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    plan TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free', 'premium')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Runs Table (Hedge Builder executions)
CREATE TABLE IF NOT EXISTS public.runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    thesis TEXT NOT NULL,
    result_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Paper Accounts Table (Virtual Cash Ledger)
CREATE TABLE IF NOT EXISTS public.paper_accounts (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    cash NUMERIC(15, 2) NOT NULL DEFAULT 100000.00 CHECK (cash >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. Orders Table (Idempotent Paper Orders)
CREATE TABLE IF NOT EXISTS public.orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    idempotency_key TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    qty INTEGER NOT NULL CHECK (qty > 0),
    price NUMERIC(15, 2) NOT NULL CHECK (price > 0),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'FILLED', 'REJECTED', 'CANCELLED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_orders_user_idempotency UNIQUE (user_id, idempotency_key)
);

-- 5. Positions Table (Active Paper Portfolio)
CREATE TABLE IF NOT EXISTS public.positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    qty INTEGER NOT NULL,
    avg_price NUMERIC(15, 2) NOT NULL CHECK (avg_price >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_positions_user_symbol UNIQUE (user_id, symbol)
);

-- 6. Risk Limits Table (Safety Controls)
CREATE TABLE IF NOT EXISTS public.risk_limits (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    max_order_value NUMERIC(15, 2) NOT NULL DEFAULT 50000.00 CHECK (max_order_value > 0),
    daily_loss_limit NUMERIC(15, 2) NOT NULL DEFAULT 10000.00 CHECK (daily_loss_limit > 0),
    kill_switch BOOLEAN NOT NULL DEFAULT false,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 7. Payments Table (Razorpay Verified Records)
CREATE TABLE IF NOT EXISTS public.payments (
    razorpay_payment_id TEXT PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    amount NUMERIC(15, 2) NOT NULL CHECK (amount > 0),
    status TEXT NOT NULL DEFAULT 'captured',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 8. Audit Log Table (Append-Only Immutable Ledger)
CREATE TABLE IF NOT EXISTS public.audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Enable Row Level Security on all tables
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.paper_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.risk_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;

-- Profiles Policies
DROP POLICY IF EXISTS "profiles_select_own" ON public.profiles;
CREATE POLICY "profiles_select_own" ON public.profiles
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "profiles_insert_own" ON public.profiles;
CREATE POLICY "profiles_insert_own" ON public.profiles
    FOR INSERT WITH CHECK (auth.uid() = user_id AND plan = 'free');

DROP POLICY IF EXISTS "profiles_update_own" ON public.profiles;
CREATE POLICY "profiles_update_own" ON public.profiles
    FOR UPDATE USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id AND plan = (SELECT plan FROM public.profiles WHERE user_id = auth.uid()));

-- Runs Policies
DROP POLICY IF EXISTS "runs_select_own" ON public.runs;
CREATE POLICY "runs_select_own" ON public.runs
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "runs_insert_own" ON public.runs;
CREATE POLICY "runs_insert_own" ON public.runs
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Paper Accounts Policies
DROP POLICY IF EXISTS "paper_accounts_select_own" ON public.paper_accounts;
CREATE POLICY "paper_accounts_select_own" ON public.paper_accounts
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "paper_accounts_update_own" ON public.paper_accounts;
CREATE POLICY "paper_accounts_update_own" ON public.paper_accounts
    FOR UPDATE USING (auth.uid() = user_id);

-- Orders Policies
DROP POLICY IF EXISTS "orders_select_own" ON public.orders;
CREATE POLICY "orders_select_own" ON public.orders
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "orders_insert_own" ON public.orders;
CREATE POLICY "orders_insert_own" ON public.orders
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "orders_update_own" ON public.orders;
CREATE POLICY "orders_update_own" ON public.orders
    FOR UPDATE USING (auth.uid() = user_id);

-- Positions Policies
DROP POLICY IF EXISTS "positions_select_own" ON public.positions;
CREATE POLICY "positions_select_own" ON public.positions
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "positions_insert_own" ON public.positions;
CREATE POLICY "positions_insert_own" ON public.positions
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "positions_update_own" ON public.positions;
CREATE POLICY "positions_update_own" ON public.positions
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "positions_delete_own" ON public.positions;
CREATE POLICY "positions_delete_own" ON public.positions
    FOR DELETE USING (auth.uid() = user_id);

-- Risk Limits Policies
DROP POLICY IF EXISTS "risk_limits_select_own" ON public.risk_limits;
CREATE POLICY "risk_limits_select_own" ON public.risk_limits
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "risk_limits_update_own" ON public.risk_limits;
CREATE POLICY "risk_limits_update_own" ON public.risk_limits
    FOR UPDATE USING (auth.uid() = user_id);

-- Payments Policies (Read-only for user; inserts via verified server/webhook)
DROP POLICY IF EXISTS "payments_select_own" ON public.payments;
CREATE POLICY "payments_select_own" ON public.payments
    FOR SELECT USING (auth.uid() = user_id);

-- Audit Log Policies (Append-only: users can select and insert their own events, no update/delete)
DROP POLICY IF EXISTS "audit_log_select_own" ON public.audit_log;
CREATE POLICY "audit_log_select_own" ON public.audit_log
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "audit_log_insert_own" ON public.audit_log;
CREATE POLICY "audit_log_insert_own" ON public.audit_log
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Auto-provision user records on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
    INSERT INTO public.profiles (user_id, plan)
    VALUES (new.id, 'free')
    ON CONFLICT (user_id) DO NOTHING;

    INSERT INTO public.paper_accounts (user_id, cash)
    VALUES (new.id, 100000.00)
    ON CONFLICT (user_id) DO NOTHING;

    INSERT INTO public.risk_limits (user_id, max_order_value, daily_loss_limit, kill_switch)
    VALUES (new.id, 50000.00, 10000.00, false)
    ON CONFLICT (user_id) DO NOTHING;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger to execute on auth.users creation
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();

-- Helper function to count today's runs for a user
CREATE OR REPLACE FUNCTION public.get_daily_run_count(p_user_id UUID)
RETURNS integer AS $$
BEGIN
    RETURN (
        SELECT COUNT(*)::integer
        FROM public.runs
        WHERE user_id = p_user_id
          AND created_at >= date_trunc('day', now())
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
