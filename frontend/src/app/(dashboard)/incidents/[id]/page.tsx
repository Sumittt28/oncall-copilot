"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { api, Incident } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ArrowLeft, Clock, User, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { format, formatDistanceToNow } from "date-fns";

const SEVERITY_VARIANTS: Record<string, "destructive" | "secondary" | "default" | "outline"> = {
  "SEV-1": "destructive",
  "SEV-2": "destructive",
  "SEV-3": "secondary",
  "SEV-4": "outline",
};

const STATUS_VARIANTS: Record<string, "destructive" | "secondary" | "default" | "outline"> = {
  open: "destructive",
  investigating: "secondary",
  identified: "secondary",
  monitoring: "default",
  resolved: "outline",
};

// Valid transitions from each status
const VALID_TRANSITIONS: Record<string, string[]> = {
  open: ["investigating", "resolved"],
  investigating: ["identified", "resolved"],
  identified: ["monitoring", "resolved"],
  monitoring: ["identified", "resolved"],
  resolved: [],
};

export default function IncidentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const incidentId = Number(params.id);

  const { data: incident, isLoading, error } = useQuery<Incident>({
    queryKey: ["incident", incidentId],
    queryFn: () => api.getIncident(incidentId),
  });

  const updateMutation = useMutation({
    mutationFn: (data: { status?: string; severity?: string }) =>
      api.updateIncident(incidentId, data as Parameters<typeof api.updateIncident>[1]),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["incident", incidentId] });
      queryClient.invalidateQueries({ queryKey: ["incidents"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("Incident updated successfully");
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="animate-pulse space-y-6">
          <div className="h-8 w-32 bg-muted rounded" />
          <div className="h-48 bg-muted rounded-lg" />
        </div>
      </div>
    );
  }

  if (error || !incident) {
    return (
      <div className="p-8">
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">Failed to load incident</p>
            <Button variant="link" onClick={() => router.push("/incidents")}>
              Back to incidents
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const validTransitions = VALID_TRANSITIONS[incident.status] || [];
  const isResolved = incident.status === "resolved";

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <Link
            href="/incidents"
            className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-2"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back to incidents
          </Link>
          <h1 className="text-2xl font-bold tracking-tight">{incident.title}</h1>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>#{incident.id}</span>
            <span>•</span>
            <Clock className="h-3 w-3" />
            <span>
              Created {formatDistanceToNow(new Date(incident.created_at), { addSuffix: true })}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={SEVERITY_VARIANTS[incident.severity]} className="text-sm">
            {incident.severity}
          </Badge>
          <Badge variant={STATUS_VARIANTS[incident.status]} className="text-sm">
            {incident.status}
          </Badge>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Description */}
          <Card>
            <CardHeader>
              <CardTitle>Description</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="whitespace-pre-wrap">{incident.description}</p>
            </CardContent>
          </Card>

          {/* Timeline */}
          <Card>
            <CardHeader>
              <CardTitle>Timeline</CardTitle>
              <CardDescription>Activity and updates on this incident</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {incident.events.length === 0 ? (
                  <p className="text-muted-foreground">No events yet</p>
                ) : (
                  incident.events.map((event) => (
                    <div key={event.id} className="flex gap-4">
                      <div className="relative">
                        <div className="w-2 h-2 rounded-full bg-primary mt-2" />
                        <div className="absolute top-4 bottom-0 left-0.5 w-px bg-border" />
                      </div>
                      <div className="flex-1 pb-4">
                        <p className="text-sm">{event.content}</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          {format(new Date(event.created_at), "MMM d, yyyy 'at' h:mm a")}
                        </p>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {!isResolved && validTransitions.length > 0 && (
                <div className="space-y-2">
                  <label className="text-sm font-medium">Update Status</label>
                  <Select
                    value={incident.status}
                    onValueChange={(value) => updateMutation.mutate({ status: value })}
                    disabled={updateMutation.isPending}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={incident.status} disabled>
                        {incident.status} (current)
                      </SelectItem>
                      {validTransitions.map((status) => (
                        <SelectItem key={status} value={status}>
                          {status}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              <div className="space-y-2">
                <label className="text-sm font-medium">Update Severity</label>
                <Select
                  value={incident.severity}
                  onValueChange={(value) => updateMutation.mutate({ severity: value })}
                  disabled={updateMutation.isPending || isResolved}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="SEV-1">SEV-1 (Critical)</SelectItem>
                    <SelectItem value="SEV-2">SEV-2 (Major)</SelectItem>
                    <SelectItem value="SEV-3">SEV-3 (Minor)</SelectItem>
                    <SelectItem value="SEV-4">SEV-4 (Low)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {isResolved && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground p-3 bg-muted rounded-lg">
                  <AlertTriangle className="h-4 w-4" />
                  <span>This incident has been resolved</span>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Details */}
          <Card>
            <CardHeader>
              <CardTitle>Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-3">
                <User className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Owner</p>
                  <p className="text-sm text-muted-foreground">{incident.owner.name}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Clock className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Created</p>
                  <p className="text-sm text-muted-foreground">
                    {format(new Date(incident.created_at), "MMM d, yyyy 'at' h:mm a")}
                  </p>
                </div>
              </div>
              {incident.resolved_at && (
                <div className="flex items-center gap-3">
                  <Clock className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm font-medium">Resolved</p>
                    <p className="text-sm text-muted-foreground">
                      {format(new Date(incident.resolved_at), "MMM d, yyyy 'at' h:mm a")}
                    </p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
