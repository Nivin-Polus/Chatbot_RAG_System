import { useState } from "react";
import { ConfirmDialog } from "@/components/ConfirmDialog";

type ConfirmActionOptions = {
  title: string;
  description?: string;
  confirmText?: string;
  cancelText?: string;
  destructive?: boolean;
  onConfirm: () => void | Promise<void>;
};

const defaultState: ConfirmActionOptions & { open: boolean } = {
  open: false,
  title: "",
  description: "",
  confirmText: "Confirm",
  cancelText: "Cancel",
  destructive: false,
  onConfirm: () => {},
};

export function useConfirmAction() {
  const [state, setState] = useState(defaultState);
  const [loading, setLoading] = useState(false);

  const openConfirm = (options: ConfirmActionOptions) => {
    setState({
      ...defaultState,
      ...options,
      open: true,
    });
  };

  const handleConfirm = async () => {
    if (!state.onConfirm) {
      setState(defaultState);
      return;
    }
    try {
      setLoading(true);
      await state.onConfirm();
    } finally {
      setLoading(false);
      setState(defaultState);
    }
  };

  const dialog = (
    <ConfirmDialog
      open={state.open}
      title={state.title}
      description={state.description}
      confirmText={state.confirmText}
      cancelText={state.cancelText}
      destructive={state.destructive}
      loading={loading}
      onConfirm={handleConfirm}
      onOpenChange={(open) =>
        setState((prev) => ({
          ...prev,
          open,
        }))
      }
    />
  );

  return { confirm: openConfirm, dialog };
}

