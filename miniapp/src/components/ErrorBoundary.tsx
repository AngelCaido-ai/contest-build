import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = {
  children: ReactNode;
  fallback?: ReactNode;
  onReset?: () => void;
};

type State = {
  hasError: boolean;
  error: Error | null;
};

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  reset = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-6 text-center">
          <span className="text-5xl">😵</span>
          <p className="text-lg font-semibold" style={{ color: "var(--tg-theme-text-color)" }}>
            Something went wrong
          </p>
          <p className="text-sm" style={{ color: "var(--tg-theme-hint-color)" }}>
            An unexpected error occurred.
            <br />
            Please try refreshing the page.
          </p>
          <button
            onClick={this.reset}
            className="mt-2 rounded-xl px-6 py-2.5 text-sm font-medium text-white"
            style={{ backgroundColor: "var(--tg-theme-button-color, #3b82f6)" }}
          >
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export function GlobalErrorFallback() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <span className="text-5xl">😵</span>
      <p className="text-lg font-semibold" style={{ color: "var(--tg-theme-text-color)" }}>
        Application cannot continue
      </p>
      <p className="text-sm" style={{ color: "var(--tg-theme-hint-color)" }}>
        A critical error occurred.
        <br />
        Please try reloading the application.
      </p>
      <button
        onClick={() => window.location.reload()}
        className="mt-2 rounded-xl px-6 py-2.5 text-sm font-medium text-white"
        style={{ backgroundColor: "var(--tg-theme-button-color, #3b82f6)" }}
      >
        Reload
      </button>
    </div>
  );
}
