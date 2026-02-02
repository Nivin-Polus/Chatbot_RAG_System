import { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { DashboardLayout } from '@/components/DashboardLayout';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Rocket, Plug, HelpCircle } from 'lucide-react';
import { PluginsContent } from './SuperadminPlugins';
import { HelpPageContent } from './SuperadminHelpPage';

export default function SuperadminDeployment() {
    const [searchParams, setSearchParams] = useSearchParams();
    const navigate = useNavigate();

    const getInitialTab = () => {
        const tabParam = searchParams.get('tab');
        if (tabParam === 'plugins' || tabParam === 'help-page') {
            return tabParam;
        }
        return 'plugins';
    };

    const [activeTab, setActiveTab] = useState<string>(getInitialTab);

    useEffect(() => {
        const tabParam = searchParams.get('tab');
        if (tabParam && (tabParam === 'plugins' || tabParam === 'help-page') && tabParam !== activeTab) {
            setActiveTab(tabParam);
        }
    }, [searchParams, activeTab]);

    const handleTabChange = (value: string) => {
        setActiveTab(value);
        const nextParams = new URLSearchParams(searchParams);
        nextParams.set('tab', value);
        setSearchParams(nextParams, { replace: true });
    };

    return (
        <DashboardLayout>
            <div className="space-y-6">
                <div className="flex flex-col gap-2">
                    <h1 className="text-3xl font-bold">Deployment</h1>
                    <p className="text-muted-foreground">
                        Manage your chatbot deployment options including plugins and standalone help pages.
                    </p>
                </div>

                <Tabs value={activeTab} onValueChange={handleTabChange} className="space-y-6">
                    <TabsList>
                        <TabsTrigger value="plugins" className="flex items-center gap-2">
                            <Plug className="h-4 w-4" />
                            Plugins
                        </TabsTrigger>
                        <TabsTrigger value="help-page" className="flex items-center gap-2">
                            <HelpCircle className="h-4 w-4" />
                            Help Page
                        </TabsTrigger>
                    </TabsList>

                    <TabsContent value="plugins" className="space-y-6">
                        <PluginsContent />
                    </TabsContent>

                    <TabsContent value="help-page" className="space-y-6">
                        <HelpPageContent />
                    </TabsContent>
                </Tabs>
            </div>
        </DashboardLayout>
    );
}
