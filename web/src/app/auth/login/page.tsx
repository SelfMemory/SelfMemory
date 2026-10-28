import { KratosFlow } from "@/components/KratosFlow";

export const metadata = { title: "Sign in" };

export default async function Login({ searchParams }: { searchParams: Promise<Record<string, string>> }) {
  return <KratosFlow type="login" params={await searchParams} />;
}
