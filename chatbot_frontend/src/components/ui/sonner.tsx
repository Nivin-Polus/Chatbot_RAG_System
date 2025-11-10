import { Toaster as Sonner, toast } from "sonner";
import { useTheme } from "@/components/ThemeProvider";

type ToasterProps = React.ComponentProps<typeof Sonner>;

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme } = useTheme();
  
  return (
    <Sonner
      theme={theme === 'system' ? 'system' : theme}
      className="toaster group"
      position="top-center"
      offset={24}
      visibleToasts={1}
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:border group-[.toaster]:shadow-xl group-[.toaster]:rounded-2xl group-[.toaster]:backdrop-blur-md group-[.toaster]:bg-background/95 group-[.toaster]:text-foreground data-[type=success]:border-emerald-500 data-[type=success]:bg-emerald-500/95 data-[type=success]:text-white data-[type=error]:border-destructive data-[type=error]:bg-destructive/95 data-[type=error]:text-white data-[type=warning]:border-amber-500 data-[type=warning]:bg-amber-500/95 data-[type=warning]:text-black data-[type=info]:border-blue-500 data-[type=info]:bg-blue-500/95 data-[type=info]:text-white",
          description: "group-[.toast]:text-muted-foreground",
          actionButton: "group-[.toast]:bg-primary group-[.toast]:text-primary-foreground",
          cancelButton: "group-[.toast]:bg-muted group-[.toast]:text-muted-foreground",
        },
      }}
      {...props}
    />
  );
};

export { Toaster, toast };
