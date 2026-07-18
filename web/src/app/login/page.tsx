"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/controls";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await api("/api/login", { method: "POST", body: JSON.stringify({ username, password }) });
      router.push("/");
    } catch (err: any) {
      toast.error(err.message || "Login gagal");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-5">
      <form onSubmit={submit} className="w-full max-w-sm">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-lg">
          <Sparkles className="h-8 w-8" />
        </div>
        <h1 className="text-center text-2xl font-bold tracking-tight">Image Bot</h1>
        <p className="mb-7 text-center text-sm text-muted-foreground">Admin Dashboard</p>
        <div className="flex flex-col gap-3">
          <Input placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
          <Input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
          <Button type="submit" size="lg" disabled={loading}>{loading ? "Memproses..." : "Masuk"}</Button>
        </div>
      </form>
    </div>
  );
}
