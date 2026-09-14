from pydantic import BaseModel, ConfigDict


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    description: str | None
    primary_label: str
    secondary_label: str


class CourseOptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    parent_id: int | None
    name: str
    slug: str
