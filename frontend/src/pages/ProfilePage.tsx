import { useCallback, useEffect, useRef, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { profileApi } from "@/lib/api";
import type { Education, Profile, WorkExperience } from "@/types";
import {
  Save,
  Plus,
  Trash2,
  Upload,
  Loader2,
  GraduationCap,
  Briefcase,
  User,
  FileText,
} from "lucide-react";

type BoolOrNull = boolean | null;

interface NewEducation {
  school: string;
  degree: string;
  field_of_study: string;
  gpa: string;
  graduation_year: number | null;
}

interface NewExperience {
  company: string;
  title: string;
  start_date: string;
  end_date: string;
  description: string;
}

const EMPTY_EDUCATION: NewEducation = {
  school: "",
  degree: "",
  field_of_study: "",
  gpa: "",
  graduation_year: null,
};

const EMPTY_EXPERIENCE: NewExperience = {
  company: "",
  title: "",
  start_date: "",
  end_date: "",
  description: "",
};

const REMOTE_OPTIONS = ["remote", "hybrid", "onsite", "any"] as const;

const EEO_STRING_OPTIONS = ["Prefer not to say", "Yes", "No"] as const;

const GENDER_OPTIONS = [
  "Prefer not to say",
  "Male",
  "Female",
  "Non-binary",
  "Other",
] as const;

const ETHNICITY_OPTIONS = [
  "Prefer not to say",
  "American Indian or Alaska Native",
  "Asian",
  "Black or African American",
  "Hispanic or Latino",
  "Native Hawaiian or Other Pacific Islander",
  "White",
  "Two or More Races",
  "Other",
] as const;

const VETERAN_OPTIONS = [
  "Prefer not to say",
  "I am not a protected veteran",
  "I identify as one or more of the classifications of a protected veteran",
] as const;

const DISABILITY_OPTIONS = [
  "Prefer not to say",
  "Yes, I have a disability (or previously had a disability)",
  "No, I do not have a disability",
] as const;

function boolToToggle(val: BoolOrNull): string {
  if (val === true) return "yes";
  if (val === false) return "no";
  return "prefer_not_to_say";
}

function toggleToBool(val: string): BoolOrNull {
  if (val === "yes") return true;
  if (val === "no") return false;
  return null;
}

function StatusMessage({
  message,
  isError,
}: {
  message: string;
  isError: boolean;
}) {
  if (!message) return null;
  return (
    <div
      className={`rounded-md px-4 py-2 text-sm ${
        isError
          ? "bg-red-50 text-red-700 border border-red-200"
          : "bg-green-50 text-green-700 border border-green-200"
      }`}
    >
      {message}
    </div>
  );
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingResume, setUploadingResume] = useState(false);
  const [addingEducation, setAddingEducation] = useState(false);
  const [addingExperience, setAddingExperience] = useState(false);
  const [deletingEducationId, setDeletingEducationId] = useState<string | null>(
    null
  );
  const [deletingExperienceId, setDeletingExperienceId] = useState<
    string | null
  >(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [isError, setIsError] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Form state for profile fields
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");

  const [desiredTitle, setDesiredTitle] = useState("");
  const [desiredLocations, setDesiredLocations] = useState("");
  const [minSalary, setMinSalary] = useState<string>("");
  const [remotePreference, setRemotePreference] = useState("any");

  const [usCitizen, setUsCitizen] = useState<string>("prefer_not_to_say");
  const [sponsorshipNeeded, setSponsorshipNeeded] =
    useState<string>("prefer_not_to_say");
  const [veteranStatus, setVeteranStatus] = useState("Prefer not to say");
  const [disabilityStatus, setDisabilityStatus] = useState("Prefer not to say");
  const [gender, setGender] = useState("Prefer not to say");
  const [ethnicity, setEthnicity] = useState("Prefer not to say");

  const [coverLetterTemplate, setCoverLetterTemplate] = useState("");

  // New education/experience forms
  const [showEducationForm, setShowEducationForm] = useState(false);
  const [newEducation, setNewEducation] =
    useState<NewEducation>(EMPTY_EDUCATION);
  const [showExperienceForm, setShowExperienceForm] = useState(false);
  const [newExperience, setNewExperience] =
    useState<NewExperience>(EMPTY_EXPERIENCE);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const showStatus = useCallback(
    (message: string, error: boolean = false) => {
      setStatusMessage(message);
      setIsError(error);
      setTimeout(() => setStatusMessage(""), 4000);
    },
    []
  );

  const populateForm = useCallback((p: Profile) => {
    setFirstName(p.first_name);
    setLastName(p.last_name);
    setEmail(p.email);
    setPhone(p.phone);
    setLinkedinUrl(p.linkedin_url);
    setWebsiteUrl(p.website_url);
    setDesiredTitle(p.desired_title);
    setDesiredLocations(p.desired_locations);
    setMinSalary(p.min_salary != null ? String(p.min_salary) : "");
    setRemotePreference(p.remote_preference || "any");
    setUsCitizen(boolToToggle(p.us_citizen));
    setSponsorshipNeeded(boolToToggle(p.sponsorship_needed));
    setVeteranStatus(p.veteran_status || "Prefer not to say");
    setDisabilityStatus(p.disability_status || "Prefer not to say");
    setGender(p.gender || "Prefer not to say");
    setEthnicity(p.ethnicity || "Prefer not to say");
    setCoverLetterTemplate(p.cover_letter_template);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function fetchProfile() {
      try {
        const data = await profileApi.get();
        if (cancelled) return;
        setProfile(data);
        populateForm(data);
      } catch (err) {
        if (cancelled) return;
        setFetchError(
          err instanceof Error ? err.message : "Failed to load profile"
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchProfile();
    return () => {
      cancelled = true;
    };
  }, [populateForm]);

  async function handleSave() {
    setSaving(true);
    try {
      const data: Partial<Profile> = {
        first_name: firstName,
        last_name: lastName,
        email,
        phone,
        linkedin_url: linkedinUrl,
        website_url: websiteUrl,
        desired_title: desiredTitle,
        desired_locations: desiredLocations,
        min_salary: minSalary ? Number(minSalary) : null,
        remote_preference: remotePreference,
        us_citizen: toggleToBool(usCitizen),
        sponsorship_needed: toggleToBool(sponsorshipNeeded),
        veteran_status: veteranStatus,
        disability_status: disabilityStatus,
        gender,
        ethnicity,
        cover_letter_template: coverLetterTemplate,
      };
      const updated = await profileApi.update(data);
      setProfile(updated);
      populateForm(updated);
      showStatus("Profile saved successfully.");
    } catch (err) {
      showStatus(
        err instanceof Error ? err.message : "Failed to save profile.",
        true
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleResumeUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadingResume(true);
    try {
      const updated = await profileApi.uploadResume(file);
      setProfile(updated);
      showStatus("Resume uploaded successfully.");
    } catch (err) {
      showStatus(
        err instanceof Error ? err.message : "Failed to upload resume.",
        true
      );
    } finally {
      setUploadingResume(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleAddEducation() {
    if (!newEducation.school || !newEducation.degree) {
      showStatus("School and degree are required.", true);
      return;
    }
    setAddingEducation(true);
    try {
      const entry = await profileApi.addEducation({
        school: newEducation.school,
        degree: newEducation.degree,
        field_of_study: newEducation.field_of_study,
        gpa: newEducation.gpa,
        graduation_year: newEducation.graduation_year,
      });
      setProfile((prev) =>
        prev ? { ...prev, education: [...prev.education, entry] } : prev
      );
      setNewEducation(EMPTY_EDUCATION);
      setShowEducationForm(false);
      showStatus("Education added.");
    } catch (err) {
      showStatus(
        err instanceof Error ? err.message : "Failed to add education.",
        true
      );
    } finally {
      setAddingEducation(false);
    }
  }

  async function handleDeleteEducation(id: string) {
    setDeletingEducationId(id);
    try {
      await profileApi.deleteEducation(id);
      setProfile((prev) =>
        prev
          ? { ...prev, education: prev.education.filter((e) => e.id !== id) }
          : prev
      );
      showStatus("Education removed.");
    } catch (err) {
      showStatus(
        err instanceof Error ? err.message : "Failed to delete education.",
        true
      );
    } finally {
      setDeletingEducationId(null);
    }
  }

  async function handleAddExperience() {
    if (!newExperience.company || !newExperience.title) {
      showStatus("Company and title are required.", true);
      return;
    }
    setAddingExperience(true);
    try {
      const entry = await profileApi.addExperience({
        company: newExperience.company,
        title: newExperience.title,
        start_date: newExperience.start_date,
        end_date: newExperience.end_date,
        description: newExperience.description,
      });
      setProfile((prev) =>
        prev
          ? { ...prev, work_experience: [...prev.work_experience, entry] }
          : prev
      );
      setNewExperience(EMPTY_EXPERIENCE);
      setShowExperienceForm(false);
      showStatus("Experience added.");
    } catch (err) {
      showStatus(
        err instanceof Error ? err.message : "Failed to add experience.",
        true
      );
    } finally {
      setAddingExperience(false);
    }
  }

  async function handleDeleteExperience(id: string) {
    setDeletingExperienceId(id);
    try {
      await profileApi.deleteExperience(id);
      setProfile((prev) =>
        prev
          ? {
              ...prev,
              work_experience: prev.work_experience.filter((e) => e.id !== id),
            }
          : prev
      );
      showStatus("Experience removed.");
    } catch (err) {
      showStatus(
        err instanceof Error ? err.message : "Failed to delete experience.",
        true
      );
    } finally {
      setDeletingExperienceId(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Card className="w-full max-w-md">
          <CardContent className="pt-6 text-center">
            <p className="text-red-600 mb-4">{fetchError}</p>
            <Button onClick={() => window.location.reload()}>Retry</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 px-4 max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Profile</h1>
          <p className="text-muted-foreground mt-1">
            Manage your personal information, preferences, and application
            materials.
          </p>
        </div>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Save className="mr-2 h-4 w-4" />
          )}
          Save Profile
        </Button>
      </div>

      {statusMessage && (
        <StatusMessage message={statusMessage} isError={isError} />
      )}

      {/* Personal Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Personal Information
          </CardTitle>
          <CardDescription>
            Basic contact details used in job applications.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="first_name">
              First Name
            </label>
            <Input
              id="first_name"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              placeholder="Jane"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="last_name">
              Last Name
            </label>
            <Input
              id="last_name"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              placeholder="Doe"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="email">
              Email
            </label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="jane@example.com"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="phone">
              Phone
            </label>
            <Input
              id="phone"
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+1 (555) 000-0000"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="linkedin_url">
              LinkedIn URL
            </label>
            <Input
              id="linkedin_url"
              type="url"
              value={linkedinUrl}
              onChange={(e) => setLinkedinUrl(e.target.value)}
              placeholder="https://linkedin.com/in/janedoe"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="website_url">
              Website URL
            </label>
            <Input
              id="website_url"
              type="url"
              value={websiteUrl}
              onChange={(e) => setWebsiteUrl(e.target.value)}
              placeholder="https://janedoe.com"
            />
          </div>
        </CardContent>
      </Card>

      {/* Job Preferences */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Briefcase className="h-5 w-5" />
            Job Preferences
          </CardTitle>
          <CardDescription>
            What you are looking for in your next role.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="desired_title">
              Desired Title
            </label>
            <Input
              id="desired_title"
              value={desiredTitle}
              onChange={(e) => setDesiredTitle(e.target.value)}
              placeholder="Software Engineer"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="desired_locations">
              Desired Locations
            </label>
            <Input
              id="desired_locations"
              value={desiredLocations}
              onChange={(e) => setDesiredLocations(e.target.value)}
              placeholder="San Francisco, New York, Remote"
            />
            <p className="text-xs text-muted-foreground">
              Comma-separated list of preferred locations.
            </p>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="min_salary">
              Minimum Salary
            </label>
            <Input
              id="min_salary"
              type="number"
              value={minSalary}
              onChange={(e) => setMinSalary(e.target.value)}
              placeholder="100000"
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="remote_preference">
              Remote Preference
            </label>
            <select
              id="remote_preference"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              value={remotePreference}
              onChange={(e) => setRemotePreference(e.target.value)}
            >
              {REMOTE_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt.charAt(0).toUpperCase() + opt.slice(1)}
                </option>
              ))}
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Standard Answers (EEO) */}
      <Card>
        <CardHeader>
          <CardTitle>Standard Answers (EEO)</CardTitle>
          <CardDescription>
            Optional equal employment opportunity responses. These are
            pre-filled on applications that ask for them. All fields default to
            "Prefer not to say."
          </CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="us_citizen">
              US Citizen
            </label>
            <select
              id="us_citizen"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              value={usCitizen}
              onChange={(e) => setUsCitizen(e.target.value)}
            >
              <option value="prefer_not_to_say">Prefer not to say</option>
              <option value="yes">Yes</option>
              <option value="no">No</option>
            </select>
          </div>
          <div className="space-y-2">
            <label
              className="text-sm font-medium"
              htmlFor="sponsorship_needed"
            >
              Sponsorship Needed
            </label>
            <select
              id="sponsorship_needed"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              value={sponsorshipNeeded}
              onChange={(e) => setSponsorshipNeeded(e.target.value)}
            >
              <option value="prefer_not_to_say">Prefer not to say</option>
              <option value="yes">Yes</option>
              <option value="no">No</option>
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="gender">
              Gender
            </label>
            <select
              id="gender"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              value={gender}
              onChange={(e) => setGender(e.target.value)}
            >
              {GENDER_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="ethnicity">
              Ethnicity
            </label>
            <select
              id="ethnicity"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              value={ethnicity}
              onChange={(e) => setEthnicity(e.target.value)}
            >
              {ETHNICITY_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="veteran_status">
              Veteran Status
            </label>
            <select
              id="veteran_status"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              value={veteranStatus}
              onChange={(e) => setVeteranStatus(e.target.value)}
            >
              {VETERAN_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="disability_status">
              Disability Status
            </label>
            <select
              id="disability_status"
              className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              value={disabilityStatus}
              onChange={(e) => setDisabilityStatus(e.target.value)}
            >
              {DISABILITY_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Education */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <GraduationCap className="h-5 w-5" />
                Education
              </CardTitle>
              <CardDescription>
                Your academic background.
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowEducationForm(true)}
              disabled={showEducationForm}
            >
              <Plus className="mr-2 h-4 w-4" />
              Add
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {profile?.education.length === 0 && !showEducationForm && (
            <p className="text-sm text-muted-foreground text-center py-4">
              No education entries yet.
            </p>
          )}

          {profile?.education.map((edu: Education) => (
            <div
              key={edu.id}
              className="flex items-start justify-between rounded-lg border p-4"
            >
              <div className="space-y-1">
                <div className="font-medium">{edu.school}</div>
                <div className="text-sm text-muted-foreground">
                  {edu.degree}
                  {edu.field_of_study ? ` in ${edu.field_of_study}` : ""}
                </div>
                <div className="flex gap-2">
                  {edu.graduation_year && (
                    <Badge variant="secondary">
                      Class of {edu.graduation_year}
                    </Badge>
                  )}
                  {edu.gpa && (
                    <Badge variant="secondary">GPA: {edu.gpa}</Badge>
                  )}
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleDeleteEducation(edu.id)}
                disabled={deletingEducationId === edu.id}
              >
                {deletingEducationId === edu.id ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4 text-red-500" />
                )}
              </Button>
            </div>
          ))}

          {showEducationForm && (
            <div className="rounded-lg border p-4 space-y-4 bg-muted/50">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">School *</label>
                  <Input
                    value={newEducation.school}
                    onChange={(e) =>
                      setNewEducation((prev) => ({
                        ...prev,
                        school: e.target.value,
                      }))
                    }
                    placeholder="MIT"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Degree *</label>
                  <Input
                    value={newEducation.degree}
                    onChange={(e) =>
                      setNewEducation((prev) => ({
                        ...prev,
                        degree: e.target.value,
                      }))
                    }
                    placeholder="Bachelor of Science"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Field of Study</label>
                  <Input
                    value={newEducation.field_of_study}
                    onChange={(e) =>
                      setNewEducation((prev) => ({
                        ...prev,
                        field_of_study: e.target.value,
                      }))
                    }
                    placeholder="Computer Science"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">GPA</label>
                  <Input
                    value={newEducation.gpa}
                    onChange={(e) =>
                      setNewEducation((prev) => ({
                        ...prev,
                        gpa: e.target.value,
                      }))
                    }
                    placeholder="3.8"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Graduation Year</label>
                  <Input
                    type="number"
                    value={
                      newEducation.graduation_year != null
                        ? String(newEducation.graduation_year)
                        : ""
                    }
                    onChange={(e) =>
                      setNewEducation((prev) => ({
                        ...prev,
                        graduation_year: e.target.value
                          ? Number(e.target.value)
                          : null,
                      }))
                    }
                    placeholder="2024"
                  />
                </div>
              </div>
              <div className="flex gap-2 justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setShowEducationForm(false);
                    setNewEducation(EMPTY_EDUCATION);
                  }}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  onClick={handleAddEducation}
                  disabled={addingEducation}
                >
                  {addingEducation ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Plus className="mr-2 h-4 w-4" />
                  )}
                  Add Education
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Work Experience */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Briefcase className="h-5 w-5" />
                Work Experience
              </CardTitle>
              <CardDescription>
                Your professional history.
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowExperienceForm(true)}
              disabled={showExperienceForm}
            >
              <Plus className="mr-2 h-4 w-4" />
              Add
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {profile?.work_experience.length === 0 && !showExperienceForm && (
            <p className="text-sm text-muted-foreground text-center py-4">
              No work experience entries yet.
            </p>
          )}

          {profile?.work_experience.map((exp: WorkExperience) => (
            <div
              key={exp.id}
              className="flex items-start justify-between rounded-lg border p-4"
            >
              <div className="space-y-1">
                <div className="font-medium">{exp.title}</div>
                <div className="text-sm text-muted-foreground">
                  {exp.company}
                </div>
                <div className="text-xs text-muted-foreground">
                  {exp.start_date}
                  {exp.end_date ? ` - ${exp.end_date}` : " - Present"}
                </div>
                {exp.description && (
                  <p className="text-sm mt-2 whitespace-pre-wrap">
                    {exp.description}
                  </p>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleDeleteExperience(exp.id)}
                disabled={deletingExperienceId === exp.id}
              >
                {deletingExperienceId === exp.id ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4 text-red-500" />
                )}
              </Button>
            </div>
          ))}

          {showExperienceForm && (
            <div className="rounded-lg border p-4 space-y-4 bg-muted/50">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Company *</label>
                  <Input
                    value={newExperience.company}
                    onChange={(e) =>
                      setNewExperience((prev) => ({
                        ...prev,
                        company: e.target.value,
                      }))
                    }
                    placeholder="Acme Corp"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Title *</label>
                  <Input
                    value={newExperience.title}
                    onChange={(e) =>
                      setNewExperience((prev) => ({
                        ...prev,
                        title: e.target.value,
                      }))
                    }
                    placeholder="Senior Software Engineer"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Start Date</label>
                  <Input
                    type="date"
                    value={newExperience.start_date}
                    onChange={(e) =>
                      setNewExperience((prev) => ({
                        ...prev,
                        start_date: e.target.value,
                      }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">End Date</label>
                  <Input
                    type="date"
                    value={newExperience.end_date}
                    onChange={(e) =>
                      setNewExperience((prev) => ({
                        ...prev,
                        end_date: e.target.value,
                      }))
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    Leave empty for current position.
                  </p>
                </div>
                <div className="space-y-2 md:col-span-2">
                  <label className="text-sm font-medium">Description</label>
                  <Textarea
                    value={newExperience.description}
                    onChange={(e) =>
                      setNewExperience((prev) => ({
                        ...prev,
                        description: e.target.value,
                      }))
                    }
                    placeholder="Key responsibilities and achievements..."
                    rows={3}
                  />
                </div>
              </div>
              <div className="flex gap-2 justify-end">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setShowExperienceForm(false);
                    setNewExperience(EMPTY_EXPERIENCE);
                  }}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  onClick={handleAddExperience}
                  disabled={addingExperience}
                >
                  {addingExperience ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Plus className="mr-2 h-4 w-4" />
                  )}
                  Add Experience
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Resume Upload */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Resume
          </CardTitle>
          <CardDescription>
            Upload your resume as a PDF file. This will be attached to
            applications.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {profile?.resume_filename && (
            <div className="flex items-center gap-2">
              <Badge variant="secondary" className="text-sm">
                <FileText className="mr-1 h-3 w-3" />
                {profile.resume_filename}
              </Badge>
            </div>
          )}
          <div className="flex items-center gap-4">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={handleResumeUpload}
              className="hidden"
              id="resume-upload"
            />
            <Button
              variant="outline"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadingResume}
            >
              {uploadingResume ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Upload className="mr-2 h-4 w-4" />
              )}
              {profile?.resume_filename ? "Replace Resume" : "Upload Resume"}
            </Button>
            <span className="text-xs text-muted-foreground">
              PDF files only
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Cover Letter Template */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Cover Letter Template
          </CardTitle>
          <CardDescription>
            Write a reusable cover letter template. Use variables that will be
            replaced automatically for each application.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            value={coverLetterTemplate}
            onChange={(e) => setCoverLetterTemplate(e.target.value)}
            placeholder={`Dear Hiring Manager,\n\nI am excited to apply for the {job_title} position at {company_name}...`}
            rows={12}
          />
          <p className="text-xs text-muted-foreground">
            Available variables:{" "}
            <code className="bg-muted px-1 py-0.5 rounded">
              {"{company_name}"}
            </code>
            ,{" "}
            <code className="bg-muted px-1 py-0.5 rounded">
              {"{job_title}"}
            </code>
          </p>
        </CardContent>
      </Card>

      {/* Bottom save button */}
      <div className="flex justify-end pb-8">
        <Button onClick={handleSave} disabled={saving} size="lg">
          {saving ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Save className="mr-2 h-4 w-4" />
          )}
          Save Profile
        </Button>
      </div>
    </div>
  );
}
