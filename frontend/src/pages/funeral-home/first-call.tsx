import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { funeralHomeService } from "@/services/funeral-home-service";
import type { FHDirector } from "@/types/funeral-home";

export default function FirstCallPage() {
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [directors, setDirectors] = useState<FHDirector[]>([]);

  // Required fields
  const [deceasedFirstName, setDeceasedFirstName] = useState("");
  const [deceasedLastName, setDeceasedLastName] = useState("");
  const [dateOfDeath, setDateOfDeath] = useState("");
  const [contactFirstName, setContactFirstName] = useState("");
  const [contactLastName, setContactLastName] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [directorId, setDirectorId] = useState("");

  // Optional fields
  const [deceasedMiddleName, setDeceasedMiddleName] = useState("");
  const [placeOfDeath, setPlaceOfDeath] = useState("");
  const [ssnLastFour, setSsnLastFour] = useState("");
  const [veteran, setVeteran] = useState(false);
  const [dispositionType, setDispositionType] = useState("");
  const [serviceType, setServiceType] = useState("");
  const [referredBy, setReferredBy] = useState("");
  const [notes, setNotes] = useState("");
  const [contactRelationship, setContactRelationship] = useState("");
  const [contactEmail, setContactEmail] = useState("");

  useEffect(() => {
    funeralHomeService.getDirectors().then(setDirectors).catch(() => {});
  }, []);

  const canSave =
    deceasedFirstName.trim() &&
    deceasedLastName.trim() &&
    dateOfDeath &&
    contactFirstName.trim() &&
    contactLastName.trim() &&
    contactPhone.trim() &&
    directorId;

  const handleSave = async () => {
    if (!canSave) return;
    setSaving(true);
    try {
      const created = await funeralHomeService.createCase({
        deceased_first_name: deceasedFirstName.trim(),
        deceased_last_name: deceasedLastName.trim(),
        deceased_middle_name: deceasedMiddleName.trim() || undefined,
        deceased_date_of_death: dateOfDeath,
        deceased_place_of_death: placeOfDeath.trim() || undefined,
        deceased_ssn_last_four: ssnLastFour.trim() || undefined,
        deceased_veteran: veteran,
        disposition_type: dispositionType || undefined,
        service_type: serviceType || undefined,
        referred_by: referredBy.trim() || undefined,
        notes: notes.trim() || undefined,
        assigned_director_id: directorId,
        primary_contact: {
          first_name: contactFirstName.trim(),
          last_name: contactLastName.trim(),
          phone_primary: contactPhone.trim(),
          relationship_to_deceased: contactRelationship.trim() || undefined,
          email: contactEmail.trim() || undefined,
        },
      });
      toast.success("First call recorded");
      navigate(`/cases/${created.id}`);
    } catch {
      toast.error("Failed to save first call");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">New First Call</h1>
        <p className="text-muted-foreground mt-1">
          Record the initial call. You can add more details later.
        </p>
      </div>

      {/* Deceased Information */}
      <Card className="border-blue-100">
        <CardHeader>
          <CardTitle>Deceased Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-5 sm:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="firstName">
                First Name <span className="text-red-500">*</span>
              </Label>
              <Input
                id="firstName"
                value={deceasedFirstName}
                onChange={(e) => setDeceasedFirstName(e.target.value)}
                placeholder="First name"
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="middleName">Middle Name</Label>
              <Input
                id="middleName"
                value={deceasedMiddleName}
                onChange={(e) => setDeceasedMiddleName(e.target.value)}
                placeholder="Middle name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="lastName">
                Last Name <span className="text-red-500">*</span>
              </Label>
              <Input
                id="lastName"
                value={deceasedLastName}
                onChange={(e) => setDeceasedLastName(e.target.value)}
                placeholder="Last name"
              />
            </div>
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="dod">
                Date of Death <span className="text-red-500">*</span>
              </Label>
              <Input
                id="dod"
                type="date"
                value={dateOfDeath}
                onChange={(e) => setDateOfDeath(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="placeOfDeath">Place of Death</Label>
              <Input
                id="placeOfDeath"
                value={placeOfDeath}
                onChange={(e) => setPlaceOfDeath(e.target.value)}
                placeholder="Hospital, home, etc."
              />
            </div>
          </div>

          <div className="grid gap-5 sm:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="ssn">SSN Last 4</Label>
              <Input
                id="ssn"
                value={ssnLastFour}
                onChange={(e) => setSsnLastFour(e.target.value.replace(/\D/g, "").slice(0, 4))}
                placeholder="1234"
                maxLength={4}
              />
            </div>
            <div className="space-y-2">
              <Label>Veteran</Label>
              <div className="pt-1">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={veteran}
                    onChange={(e) => setVeteran(e.target.checked)}
                    className="h-4 w-4 rounded border-gray-300"
                  />
                  <span className="text-sm">Yes, veteran</span>
                </label>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="referredBy">Referred By</Label>
              <Input
                id="referredBy"
                value={referredBy}
                onChange={(e) => setReferredBy(e.target.value)}
                placeholder="Referral source"
              />
            </div>
          </div>

          <div className="grid gap-5 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="disposition">Disposition Type</Label>
              <select
                id="disposition"
                value={dispositionType}
                onChange={(e) => setDispositionType(e.target.value)}
                className="w-full rounded-md border border-input px-3 py-2 text-sm"
              >
                <option value="">Select...</option>
                <option value="burial">Burial</option>
                <option value="cremation">Cremation</option>
                <option value="entombment">Entombment</option>
                <option value="donation">Donation</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="serviceType">Service Type</Label>
              <select
                id="serviceType"
                value={serviceType}
                onChange={(e) => setServiceType(e.target.value)}
                className="w-full rounded-md border border-input px-3 py-2 text-sm"
              >
                <option value="">Select...</option>
                <option value="traditional">Traditional Service</option>
                <option value="memorial">Memorial Service</option>
                <option value="graveside">Graveside Service</option>
                <option value="celebration_of_life">Celebration of Life</option>
                <option value="direct_burial">Direct Burial</option>
                <option value="direct_cremation">Direct Cremation</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Primary Contact */}
      <Card className="border-green-100">
        <CardHeader>
          <CardTitle>Primary Contact</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="grid gap-5 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="contactFirst">
                First Name <span className="text-red-500">*</span>
              </Label>
              <Input
                id="contactFirst"
                value={contactFirstName}
                onChange={(e) => setContactFirstName(e.target.value)}
                placeholder="First name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="contactLast">
                Last Name <span className="text-red-500">*</span>
              </Label>
              <Input
                id="contactLast"
                value={contactLastName}
                onChange={(e) => setContactLastName(e.target.value)}
                placeholder="Last name"
              />
            </div>
          </div>
          <div className="grid gap-5 sm:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="contactPhone">
                Phone <span className="text-red-500">*</span>
              </Label>
              <Input
                id="contactPhone"
                type="tel"
                value={contactPhone}
                onChange={(e) => setContactPhone(e.target.value)}
                placeholder="(555) 555-5555"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="contactEmail">Email</Label>
              <Input
                id="contactEmail"
                type="email"
                value={contactEmail}
                onChange={(e) => setContactEmail(e.target.value)}
                placeholder="email@example.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="contactRel">Relationship</Label>
              <Input
                id="contactRel"
                value={contactRelationship}
                onChange={(e) => setContactRelationship(e.target.value)}
                placeholder="Spouse, child, etc."
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Assignment & Notes */}
      <Card>
        <CardHeader>
          <CardTitle>Assignment</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-2">
            <Label htmlFor="director">
              Assigned Director <span className="text-red-500">*</span>
            </Label>
            <select
              id="director"
              value={directorId}
              onChange={(e) => setDirectorId(e.target.value)}
              className="w-full rounded-md border border-input px-3 py-2 text-sm"
            >
              <option value="">Select a director...</option>
              {directors.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.first_name} {d.last_name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="notes">Notes</Label>
            <textarea
              id="notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={3}
              className="w-full rounded-md border border-input px-3 py-2 text-sm resize-none"
              placeholder="Any initial notes from the call..."
            />
          </div>
        </CardContent>
      </Card>

      {/* Save */}
      <div className="flex justify-end gap-3">
        <Button variant="outline" onClick={() => navigate("/cases")}>
          Cancel
        </Button>
        <Button size="lg" disabled={!canSave || saving} onClick={handleSave}>
          {saving ? "Saving..." : "Save First Call"}
        </Button>
      </div>
    </div>
  );
}
