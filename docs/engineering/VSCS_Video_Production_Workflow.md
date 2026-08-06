VSCS Video Production Workflow
1. Create the project and define the production

The user creates a project and specifies what is being produced:

Trailer
Short film
Episode
Feature film
Promotional video

They define:

Title
Target duration
Aspect ratio
Frame rate
Preview and Production quality
Intended release platform
Production status

Output: A production container with technical and creative targets.

2. Upload or create the story

The source may be:

Manuscript
Screenplay
Story outline
Episode outline
Original concept entered directly into VSCS

VSCS stores the source and identifies:

Story structure
Characters
Locations
Props
Ships and vehicles
Dialogue
Major events
Required effects
Potential continuity information

Automated extraction should be treated as a proposal until approved.

Output: Structured story source and initial production requirements.

3. Break the story into production structure

The story is organised into:

Production
→ Episode or Film
→ Sequence
→ Scene
→ Shot
→ Clip, where required

For a trailer, the structure may be:

Trailer
→ Trailer Beats
→ Scenes
→ Shots
→ Clips

At this stage, scenes describe what happens, while shots describe how the audience sees it.

Output: Approved narrative and production hierarchy.

4. Identify and define required assets

VSCS generates an asset requirement list from the scenes and shots.

Examples:

Commander James Spence
Iron Horizon
Xorix City
Guild uniforms
Shuttle interior
Bridge consoles
Engine trails
Voice profiles
Camera profiles
Lighting profiles

Each requirement is matched against the existing Asset Library.

The user decides whether to:

Reuse an existing asset
Create a new asset
Create an approved variant
Mark it temporarily unresolved

Output: Complete asset requirement and reuse plan.

5. Create and manage assets

New assets are created in the Asset Manager.

The Asset Manager must support the full lifecycle:

Create
View
Edit
Duplicate
Tag
Search
Create variants
Archive
Inspect usage
Inspect dependencies

The asset record identifies what the object is, but it does not yet contain the complete canonical production description.

Output: Registered production assets with stable IDs.

6. Create and approve CAPs and canonical references

Each recurring visual or audio asset receives its authoritative production identity.

The CAP defines:

Canonical description
Appearance
Dimensions
Materials
Colours
Behaviour
Movement rules
Production restrictions
Forbidden interpretations
Physical constraints
Voice identity where relevant

Canonical references define what the asset should look or sound like.

At minimum, a visual asset normally requires:

Approved asset
Approved CAP
Approved primary reference

Output: Production-ready canonical assets.

7. Create scenes and shots

Each scene defines:

Narrative purpose
Location
Time
Characters
Actions
Dialogue
Required assets
Emotional state
Entry continuity
Exit continuity

Each shot defines:

Shot purpose
Duration
Camera framing
Lens
Camera movement
Blocking
Lighting
Dialogue
Effects
Required assets
Physical reality constraints
Continuity source
Continuity result

The combined shot durations should cover the intended scene and production runtime.

Output: Complete cinematic shot plan.

8. Production planning

This is the part that needs the clearest definition.

Production planning is not creating the scenes or shots again. It determines whether the planned production can actually be executed, and in what order.

It answers:

What needs to be ready before this shot can be produced?

For each shot, production planning evaluates:

Are all required assets registered?
Are their CAPs approved?
Are canonical references available?
Is dialogue complete?
Is the voice profile assigned?
Is continuity from the previous shot defined?
Are camera and lighting instructions complete?
Are physical reality constraints defined?
Which ComfyUI workflow is required?
Does that workflow support the shot?
Is Preview or Production quality required?
How long is the render likely to take?
Which shots depend on earlier outputs?
Can shots be rendered in parallel?
Which shot must provide the end frame for the next shot?
Is lip-sync required?
Is audio required?
Where will outputs be stored?
What approval is required before proceeding?

Production planning then creates:

Production order
Dependency order
Render batches
Preview schedule
Production-render schedule
Audio schedule
Lip-sync schedule
QC schedule
Estimated processing time
Blocked-work list
Example

Story order:

Shot 1 → Shot 2 → Shot 3

Production order might be:

Render Shot 1 preview
Render Shot 3 establishing preview
Approve character asset
Render Shot 2 preview
Approve all previews
Render Shot 1 production
Use Shot 1 end frame for Shot 2
Render Shot 2 production
Render Shot 3 production

So production planning converts the creative plan into an executable production plan.

Output: Validated, scheduled and dependency-aware production plan.

9. Build the shot production package

For every shot, VSCS creates the ACPP package.

It combines:

Story intent
Shot details
Asset bindings
CAP descriptions
Canonical references
Camera
Lighting
Blocking
Dialogue
Voice
Continuity
Physical reality
Effects
Quality profile
Output settings

Output: Validated renderer-neutral shot package.

10. Compile the prompt and rendering workflow

VSCS converts the ACPP into:

Prompt Graph
Positive prompt
Negative prompt
Reference-image bindings
Renderer profile
ComfyUI workflow
Workflow parameters
Output path and filename
Dependency fingerprint

Output: Renderer-ready package.

11. Generate and approve previews

VSCS submits lower-cost Preview jobs first.

The user reviews:

Character and asset identity
Composition
Camera movement
Lighting
Physical plausibility
Continuity
Timing
Prompt accuracy
Major visual artifacts

Possible results:

Approve
Revise Prompt
Revise Shot
Revise Asset or CAP
Reject

Output: Approved preview or revision request.

12. Generate production video shots

Approved previews are rendered using the Production quality profile.

VSCS manages:

Queueing
Workflow submission
Progress
Retries
Recovery
Output registration
Start and end frames
Versions
Render metadata

Output: Production-quality raw video shots.

13. Create dialogue and lip-sync

Dialogue production includes:

Voice assignment
Voice generation or recording
Pronunciation
Emotional direction
Timing
Audio cleanup
Loudness normalisation

Lip-sync is then applied to shots where visible characters speak.

It is generally best handled after the main video render, because that allows:

Better control of the voice performance
Reuse of approved video
Independent correction of dialogue
Specialist close-up and multi-speaker processing

Output: Dialogue-complete, lip-synchronised shots.

14. Add sound and music

Each shot or scene receives:

Dialogue
Ambience
Foley
Machinery or ship sounds
Effects
Music
Narration where required

Audio must preserve continuity between adjoining shots.

Output: Complete audio-equipped shots or scene stems.

15. Perform shot quality control

Every shot is checked for:

Story accuracy
Character identity
Asset consistency
Continuity
Physical plausibility
Motion quality
Visual artifacts
Dialogue
Lip-sync
Audio
Resolution
Duration
Frame rate
File integrity

Each shot becomes:

Approved
Revision Required
Rejected

Output: Approved production shots.

16. Assemble the final video

Approved shots are placed onto a timeline.

The system supports:

Shot ordering
Trimming
Transitions
Dialogue alignment
Audio tracks
Music
Titles
Captions
Credits
Colour consistency
Runtime validation

For a trailer, this also includes:

Trailer pacing
Title cards
Release message
Call to action
Spoiler control

Output: Complete production edit.

17. Finalise and master

Finalisation includes:

Colour grading
Audio mixing
Artifact cleanup
Titles and credits
Subtitles
Captions
Final quality assurance
Platform compliance
Master encoding

Output: Approved release master.

18. Export and release

VSCS produces the required deliverables:

Streaming master
Trailer
Social-media versions
Vertical clips
Review copy
Subtitle files
Archive package

It records:

Output version
Checksum
Release destination
Publication status
Archive location

Output: Published and archived production.

The simplified user path

From the user's perspective, it should feel like this:

Create Project
→ Add Story
→ Approve Story Structure
→ Resolve Assets
→ Approve CAPs and References
→ Approve Scenes and Shots
→ Validate Production Plan
→ Generate Previews
→ Approve Previews
→ Generate Production Shots
→ Add Dialogue and Lip-sync
→ Approve Shots
→ Assemble Video
→ Final QA
→ Export and Release

The user should not have to manually think about Prompt Graphs, dependency checksums, manifests, batch history or recovery unless something needs attention. Those are internal VSCS engineering capabilities supporting the workflow.

The key clarification

Your original step 6, Production Planning, sits between creative planning and execution:

Scenes and Shots
        ↓
Production Planning
        ↓
Video Generation

Its purpose is to confirm that everything required to render the shots exists, determine the correct processing order, calculate dependencies, group work into batches and identify anything blocking production.

That means the next P0 work should not start by inventing another planning module blindly. It should first ensure the application supports this complete chain:

Production
→ Scene
→ Shot
→ Readiness
→ Dependencies
→ Executable Production Plan

That is the exact production-planning boundary we need to implement next.