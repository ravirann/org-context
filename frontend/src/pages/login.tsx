import { useMutation } from "@tanstack/react-query";
import { KeyRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { useToast } from "@/components/ui/toast";
import { usePageTitle } from "@/hooks/use-page-title";
import { api, isApiError } from "@/lib/api";
import type { AuthLoginResponse } from "@/lib/types";

/**
 * Full-screen SSO login. Rendered by App.tsx when auth_mode==="oidc" and the
 * session is unauthenticated, and also mounted at the /login route directly.
 */
export default function LoginPage() {
  usePageTitle("Sign in");
  const { toast } = useToast();

  const mutation = useMutation({
    mutationFn: () => api.get<AuthLoginResponse>("/v1/auth/login"),
    onSuccess: (data) => {
      window.location.href = data.authorization_url;
    },
    onError: (error) => {
      toast({
        title: "Sign-in failed",
        description: isApiError(error) ? error.detail : "Could not start SSO sign-in.",
        variant: "error",
      });
    },
  });

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-background p-4">
      <div data-testid="page-login" className="w-full max-w-sm">
        <Card>
          <CardHeader className="items-center gap-2 p-6 pb-2 text-center">
            <div className="flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <KeyRound className="size-5" aria-hidden="true" />
            </div>
            <CardTitle className="text-base">Org Context Platform</CardTitle>
            <CardDescription>
              Sign in with your organization's identity provider to access the context
              engineering platform.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 p-6 pt-4">
            <Button
              className="w-full"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending ? (
                <Spinner className="text-primary-foreground" />
              ) : null}
              Sign in with SSO
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
