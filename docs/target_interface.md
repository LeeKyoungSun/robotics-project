Input:
    object_name (str)

Static:
    ball / bowl / bed / chair / car

Dynamic:
    dog / cat / person\

Output:
{
    type: static | dynamic,
    object: str,
    target: str,
    pose: {
        frame_id,
        x,
        y,
        yaw
    }
}